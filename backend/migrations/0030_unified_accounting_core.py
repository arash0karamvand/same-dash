from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_factory_permissions(apps, schema_editor):
    Permission = apps.get_model("backend", "Permission")
    RolePermission = apps.get_model("backend", "RolePermission")
    UserPermission = apps.get_model("backend", "UserPermission")
    mapping = {
        "view_factory_accounting": "view_accounting",
        "create_factory_accounting": "create_accounting",
        "edit_factory_accounting": "edit_accounting",
        "delete_factory_accounting": "delete_accounting",
        "approve_factory_accounting": "approve_accounting",
    }
    for legacy_code, unified_code in mapping.items():
        legacy = Permission.objects.filter(code=legacy_code).first()
        if legacy is None:
            continue
        unified, _created = Permission.objects.get_or_create(
            code=unified_code,
            defaults={"label": unified_code, "description": ""},
        )
        for row in RolePermission.objects.filter(permission=legacy):
            RolePermission.objects.get_or_create(role_id=row.role_id, permission=unified)
        for row in UserPermission.objects.filter(permission=legacy):
            UserPermission.objects.get_or_create(
                access_profile_id=row.access_profile_id,
                permission=unified,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0029_opening_entry_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="vat_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="sale",
            name="vat_amount",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18),
        ),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.CheckConstraint(
                condition=models.Q(vat_rate__gte=0), name="ck_order_vat_rate"
            ),
        ),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.CheckConstraint(
                condition=models.Q(vat_amount__gte=0), name="ck_order_vat_amount"
            ),
        ),
        migrations.AddField(
            model_name="materialstocktake",
            name="journal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="material_stocktakes",
                to="backend.journalentry",
            ),
        ),
        migrations.AddField(
            model_name="assistancerequest",
            name="journal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assistance_requests",
                to="backend.journalentry",
            ),
        ),
        migrations.AddField(
            model_name="pettycashrequest",
            name="journal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="petty_cash_requests",
                to="backend.journalentry",
            ),
        ),
        migrations.AddField(
            model_name="wipclose",
            name="material_cost",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18),
        ),
        migrations.AddField(
            model_name="wipclose",
            name="labor_cost",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18),
        ),
        migrations.AddField(
            model_name="wipclose",
            name="overhead_cost",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18),
        ),
        migrations.AddField(
            model_name="wipclose",
            name="journal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="wip_closes",
                to="backend.journalentry",
            ),
        ),
        migrations.AddConstraint(
            model_name="wipclose",
            constraint=models.CheckConstraint(
                condition=models.Q(material_cost__gte=0), name="ck_wip_material_cost"
            ),
        ),
        migrations.AddConstraint(
            model_name="wipclose",
            constraint=models.CheckConstraint(
                condition=models.Q(labor_cost__gte=0), name="ck_wip_labor_cost"
            ),
        ),
        migrations.AddConstraint(
            model_name="wipclose",
            constraint=models.CheckConstraint(
                condition=models.Q(overhead_cost__gte=0), name="ck_wip_overhead_cost"
            ),
        ),
        migrations.CreateModel(
            name="FinancialEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_module", models.CharField(max_length=40)),
                ("source_type", models.CharField(max_length=80)),
                ("source_key", models.CharField(max_length=120)),
                ("event_type", models.CharField(max_length=60)),
                ("rule_version", models.CharField(default="1", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "در انتظار صدور"),
                            ("drafted", "پیش‌نویس صادر شد"),
                            ("posted", "ثبت قطعی شد"),
                            ("failed", "خطا"),
                            ("void", "باطل"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "journal",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="financial_events",
                        to="backend.journalentry",
                    ),
                ),
            ],
            options={"ordering": ["-occurred_at", "-id"]},
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date_from", models.DateField()),
                ("date_to", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "باز"), ("closed", "بسته"), ("reopened", "بازگشایی‌شده")],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "closed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="closed_accounting_periods",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ledger",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="periods",
                        to="backend.ledger",
                    ),
                ),
            ],
            options={"ordering": ["-date_from"]},
        ),
        migrations.CreateModel(
            name="LedgerMigrationAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("batch_id", models.UUIDField()),
                ("action", models.CharField(max_length=40)),
                ("entity_type", models.CharField(max_length=80)),
                ("entity_id", models.CharField(max_length=120)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["batch_id", "id"]},
        ),
        migrations.AddConstraint(
            model_name="financialevent",
            constraint=models.UniqueConstraint(
                fields=("source_module", "source_type", "source_key", "event_type"),
                name="uq_financial_event_source",
            ),
        ),
        migrations.AddIndex(
            model_name="financialevent",
            index=models.Index(fields=["status", "occurred_at"], name="ix_fin_event_status"),
        ),
        migrations.AddIndex(
            model_name="financialevent",
            index=models.Index(fields=["source_module", "source_type"], name="ix_fin_event_source"),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.UniqueConstraint(
                fields=("ledger", "date_from", "date_to"), name="uq_accounting_period"
            ),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(date_to__gte=models.F("date_from")),
                name="ck_accounting_period_dates",
            ),
        ),
        migrations.AddIndex(
            model_name="ledgermigrationaudit",
            index=models.Index(fields=["batch_id", "action"], name="ix_ledger_migration"),
        ),
        migrations.RunPython(migrate_factory_permissions, migrations.RunPython.noop),
    ]
