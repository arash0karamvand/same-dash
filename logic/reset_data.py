"""پاک‌سازی کامل داده‌ها — حذف فیزیکی (hard delete)؛ فقط مدیر سیستم حفظ می‌شود."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection, transaction

from auth import roles
from auth.roles import ADMIN
from backend.models import (
    BirthdaySmsSettings,
    SmsClubSettings,
    StaffProfile,
    UserAccessProfile,
    UserPermission,
)
from logic.ledger import ensure_ledgers

User = get_user_model()

# پیکربندی لازم برای بالا آمدن پنل. داده‌های عملیاتی این‌جا نیستند.
STRUCTURAL_LABELS = frozenset(
    {
        "contenttypes.ContentType",
        "auth.Permission",
        "auth.Group",
        "backend.Branch",
        "backend.LookupOption",
        "backend.PaymentMethod",
        "backend.PaymentStatus",
        "backend.OrderKind",
        "backend.OrderStatus",
        "backend.AccountingMode",
        "backend.InstallmentStatus",
        "backend.AttendanceStatus",
        "backend.ApprovalStatus",
        "backend.MaterialStatus",
        "backend.SmsStatus",
        "backend.SmsType",
        "backend.JournalEntryType",
        "backend.JournalEntryStatus",
        "backend.Permission",
        "backend.RoleDefinition",
        "backend.RolePermission",
        "backend.RoleClosure",
        "backend.MenuSection",
        "backend.MenuPermission",
        "backend.SectionPermission",
        "backend.WorkflowStage",
        "backend.AuditEntityType",
    }
)


def admin_user_ids():
    """شناسه کاربرانی که باید حفظ شوند (superuser یا نقش مدیر سیستم)."""
    ids = set(User.objects.filter(is_superuser=True).values_list("pk", flat=True))
    for user in User.objects.only("id").iterator():
        if roles.get_user_role(user) == ADMIN:
            ids.add(user.id)
    return ids


def _quote(name):
    return connection.ops.quote_name(name)


def _concrete_models():
    for model in apps.get_models(include_auto_created=False):
        opts = model._meta
        if opts.proxy or not opts.managed:
            continue
        yield model


def _auto_m2m_tables(model):
    tables = []
    for field in model._meta.local_many_to_many:
        through = field.remote_field.through
        if through._meta.auto_created:
            tables.append(through._meta.db_table)
    return tables


def _user_column(through_model):
    for field in through_model._meta.concrete_fields:
        remote = getattr(getattr(field, "remote_field", None), "model", None)
        if remote is User:
            return field.column
    return None


def _nullable_user_or_wiped_fks(model):
    for field in model._meta.concrete_fields:
        remote = getattr(getattr(field, "remote_field", None), "model", None)
        if remote is not None and field.many_to_one and field.null:
            yield field, remote


def _delete_all(cursor, table):
    cursor.execute(f"DELETE FROM {_quote(table)}")
    return max(cursor.rowcount, 0)


def _delete_except(cursor, table, column, keep_ids):
    marks = ", ".join(["%s"] * len(keep_ids))
    cursor.execute(
        f"DELETE FROM {_quote(table)} WHERE {_quote(column)} NOT IN ({marks})",
        list(keep_ids),
    )
    return max(cursor.rowcount, 0)


def _trigger_statements(cursor):
    """تعریف تریگرهای فعلی تا بعد از حذف فیزیکی دوباره ساخته شوند."""
    cursor.execute(
        "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()"
    )
    names = [row[0] for row in cursor.fetchall()]
    statements = []
    for name in names:
        cursor.execute(f"SHOW CREATE TRIGGER {_quote(name)}")
        description = cursor.description or []
        columns = [col[0] for col in description]
        row = cursor.fetchone()
        payload = dict(zip(columns, row))
        create_sql = payload.get("SQL Original Statement") or payload.get("Create Trigger")
        if not create_sql:
            raise RuntimeError(f"تعریف تریگر {name} خوانده نشد.")
        statements.append((name, payload.get("sql_mode") or "", create_sql))
    return statements


def _drop_triggers(cursor, statements):
    for name, _mode, _sql in statements:
        cursor.execute(f"DROP TRIGGER IF EXISTS {_quote(name)}")


def _restore_triggers(cursor, statements):
    if not statements:
        return
    cursor.execute("SELECT @@SESSION.sql_mode")
    previous_mode = cursor.fetchone()[0]
    try:
        for _name, sql_mode, create_sql in statements:
            if sql_mode:
                cursor.execute("SET SESSION sql_mode=%s", [sql_mode])
            cursor.execute(create_sql)
    finally:
        cursor.execute("SET SESSION sql_mode=%s", [previous_mode])


def _disable_fk_checks(cursor):
    if connection.vendor != "mysql":
        raise RuntimeError("پاکسازی سخت فقط روی MySQL پشتیبانی می‌شود.")
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")


def _enable_fk_checks(cursor):
    if connection.vendor == "mysql":
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")


def reset_business_data(*, keep_session_key=None, extra_keep_ids=()):
    """
    حذف فیزیکی همه داده‌های عملیاتی.

    کاربران مدیر سیستم (و superuser) حفظ می‌شوند.
    تعاریف نقش، شعب، منو، مراحل گردش و lookupها حفظ می‌شوند تا پنل قابل استفاده بماند.
    دفترهای خالی اداری و کارخانه دوباره ساخته می‌شوند؛ کدینگ و اسناد حذف می‌شوند.
    """
    keep_ids = admin_user_ids()
    keep_ids.update(int(pk) for pk in extra_keep_ids if pk)
    if not keep_ids:
        raise RuntimeError("هیچ حساب مدیر سیستمی برای حفظ کردن پیدا نشد.")

    partial_labels = {
        User._meta.label,
        StaffProfile._meta.label,
        UserAccessProfile._meta.label,
        UserPermission._meta.label,
        Session._meta.label,
    }
    wipe_tables = []
    kept_models = []
    seen = set()

    def add_table(table):
        if table not in seen:
            seen.add(table)
            wipe_tables.append(table)

    for model in _concrete_models():
        label = model._meta.label
        if label in STRUCTURAL_LABELS or label in partial_labels:
            kept_models.append(model)
            continue
        add_table(model._meta.db_table)
        for table in _auto_m2m_tables(model):
            add_table(table)

    counts = {
        "tables_cleared": len(wipe_tables),
        "rows_deleted": 0,
        "users_deleted": 0,
        "admin_users_kept": len(keep_ids),
        "sessions_cleared": 0,
    }
    marks = ", ".join(["%s"] * len(keep_ids))
    keep_params = list(keep_ids)

    # DROP/CREATE TRIGGER در MySQL کامیت ضمنی دارد؛ حذف فیزیکی باید بیرون از savepoint بماند.
    with connection.cursor() as cursor:
        trigger_sql = _trigger_statements(cursor)
        _drop_triggers(cursor, trigger_sql)
        _disable_fk_checks(cursor)
        try:
            with transaction.atomic():
                for table in wipe_tables:
                    counts["rows_deleted"] += _delete_all(cursor, table)

                counts["staff_profiles"] = _delete_except(
                    cursor, StaffProfile._meta.db_table, StaffProfile._meta.get_field("user").column, keep_ids
                )
                profile_table = UserAccessProfile._meta.db_table
                perm_table = UserPermission._meta.db_table
                perm_col = UserPermission._meta.get_field("access_profile").column
                profile_pk = UserAccessProfile._meta.pk.column
                cursor.execute(
                    f"DELETE FROM {_quote(perm_table)} "
                    f"WHERE {_quote(perm_col)} NOT IN ("
                    f"SELECT {_quote(profile_pk)} FROM {_quote(profile_table)} "
                    f"WHERE {_quote('user_id')} IN ({marks}))",
                    keep_params,
                )
                counts["user_permissions"] = max(cursor.rowcount, 0)
                counts["access_profiles"] = _delete_except(
                    cursor, profile_table, UserAccessProfile._meta.get_field("user").column, keep_ids
                )

                for through in (User.groups.through, User.user_permissions.through):
                    column = _user_column(through)
                    if column:
                        _delete_except(cursor, through._meta.db_table, column, keep_ids)

                counts["users_deleted"] = _delete_except(
                    cursor, User._meta.db_table, User._meta.pk.column, keep_ids
                )
                counts["rows_deleted"] += counts["users_deleted"]

                wiped = set(wipe_tables)
                for model in kept_models:
                    table = model._meta.db_table
                    for field, remote in _nullable_user_or_wiped_fks(model):
                        column = field.column
                        if remote._meta.db_table in wiped:
                            cursor.execute(
                                f"UPDATE {_quote(table)} SET {_quote(column)} = NULL "
                                f"WHERE {_quote(column)} IS NOT NULL"
                            )
                        elif remote is User:
                            cursor.execute(
                                f"UPDATE {_quote(table)} SET {_quote(column)} = NULL "
                                f"WHERE {_quote(column)} IS NOT NULL "
                                f"AND {_quote(column)} NOT IN ({marks})",
                                keep_params,
                            )

                session_table = Session._meta.db_table
                session_pk = Session._meta.pk.column
                if keep_session_key:
                    cursor.execute(
                        f"DELETE FROM {_quote(session_table)} WHERE {_quote(session_pk)} <> %s",
                        [keep_session_key],
                    )
                else:
                    cursor.execute(f"DELETE FROM {_quote(session_table)}")
                counts["sessions_cleared"] = max(cursor.rowcount, 0)
        finally:
            _enable_fk_checks(cursor)
            _restore_triggers(cursor, trigger_sql)

    BirthdaySmsSettings.get_solo()
    SmsClubSettings.get_solo()
    ensure_ledgers()

    return counts
