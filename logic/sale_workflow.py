"""گردش کار سفارش — جداول جدا: فروشگاه → اداری → کارخانه."""

from django.db import transaction
from django.utils import timezone

STAGE_PENDING_BRANCH = "pending_branch"
STAGE_BRANCH_APPROVED = "branch_approved"
STAGE_ACCOUNTING_APPROVED = "accounting_approved"
STAGE_IN_PRODUCTION = "in_production"
STAGE_PRODUCTION_DONE = "production_done"
STAGE_IN_FREIGHT = "in_freight"
STAGE_IN_WAREHOUSE = "in_warehouse"
STAGE_READY_FOR_PICKUP = "ready_for_pickup"
STAGE_MERCHANT_ASSIGNED = "merchant_assigned"
STAGE_COMPLETED = "completed"

WORKFLOW_STAGE_LABELS = {
    STAGE_PENDING_BRANCH: "صف فروشگاه",
    STAGE_BRANCH_APPROVED: "صف اداری",
    STAGE_ACCOUNTING_APPROVED: "ارسال به کارخانه",
    STAGE_IN_PRODUCTION: "در حال ساخت",
    STAGE_PRODUCTION_DONE: "آماده باربری",
    STAGE_IN_FREIGHT: "در باربری",
    STAGE_IN_WAREHOUSE: "در انبار",
    STAGE_READY_FOR_PICKUP: "آماده تحویل حضوری",
    STAGE_MERCHANT_ASSIGNED: "بازرگان — صف کارخانه",
    STAGE_COMPLETED: "تکمیل شده",
}

WORKFLOW_STAGE_PROGRESS = {
    STAGE_PENDING_BRANCH: 10,
    STAGE_BRANCH_APPROVED: 25,
    STAGE_ACCOUNTING_APPROVED: 40,
    STAGE_IN_PRODUCTION: 60,
    STAGE_PRODUCTION_DONE: 80,
    STAGE_IN_FREIGHT: 92,
    STAGE_IN_WAREHOUSE: 55,
    STAGE_READY_FOR_PICKUP: 70,
    STAGE_MERCHANT_ASSIGNED: 40,
    STAGE_COMPLETED: 100,
}


def workflow_progress_percent(stage):
    return WORKFLOW_STAGE_PROGRESS.get(stage, 0)

BRANCH_MASK_STAGES = {
    STAGE_BRANCH_APPROVED,
    STAGE_ACCOUNTING_APPROVED,
    STAGE_IN_PRODUCTION,
    STAGE_PRODUCTION_DONE,
    STAGE_IN_FREIGHT,
    STAGE_IN_WAREHOUSE,
    STAGE_READY_FOR_PICKUP,
    STAGE_MERCHANT_ASSIGNED,
    STAGE_COMPLETED,
}


def uses_workflow_on_create(user):
    """همه سفارش‌های ثبت‌شده تا تایید سرپرست/مدیر در صف فروشگاه می‌مانند."""
    return user is not None and getattr(user, "is_authenticated", False)


def auto_approve_branch_on_create(user):
    """همه سفارش‌ها تا تایید سرپرست معلق می‌مانند."""
    return False


def is_workflow_sale(sale):
    return sale.workflow_stage_id != STAGE_COMPLETED or sale.order_status == sale.ORDER_STATUS_PENDING


@transaction.atomic
def approve_sale_branch(sale, user):
    from backend.models import Sale
    from logic.order_queues import create_office_order_from_sale

    if sale.workflow_stage_id != STAGE_PENDING_BRANCH:
        raise ValueError("این سفارش در مرحله تایید سرپرست شعبه نیست.")
    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    create_office_order_from_sale(sale, user)
    sale.refresh_from_db()
    return sale


@transaction.atomic
def approve_office_order(
    office_order,
    user,
    *,
    check_registration_account_id=None,
    check_deposit_account_id=None,
    save_check_accounts_as_default=False,
    fulfillment_route=None,
    warehouse_id=None,
    source_branch=None,
    merchant_user_id=None,
):
    from logic.check_accounting import (
        _resolve_account,
        register_sale_checks,
        sale_has_pending_checks,
        save_user_accounting_preference,
    )
    from logic.order_cycle import (
        ROUTE_FACTORY,
        apply_fulfillment_fields,
        fulfillment_note,
    )
    from logic.order_queues import create_factory_order_from_office, route_office_order
    from logic.sales import _apply_purchase_to_customer, _create_sale_accounting, balance_due

    if office_order.status != office_order.STATUS_PENDING:
        raise ValueError("این سفارش در مرحله تایید اداری نیست.")

    sale = office_order.source_sale
    if sale.order_status == sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    has_checks = sale_has_pending_checks(sale)
    if has_checks and not check_registration_account_id:
        raise ValueError("برای سفارش چکی، انتخاب حساب ثبت چک الزامی است.")

    fields = apply_fulfillment_fields(
        sale,
        route=fulfillment_route,
        warehouse_id=warehouse_id,
        source_branch=source_branch,
        merchant_user_id=merchant_user_id,
    )
    route = fields["fulfillment_route"]
    note = fulfillment_note(
        route,
        warehouse=fields["fulfillment_warehouse"],
        source_branch=fields["fulfillment_source_branch"],
        merchant=fields["merchant_user"],
    )
    if route == ROUTE_FACTORY:
        create_factory_order_from_office(office_order, user)
        sale.refresh_from_db()
        sale.fulfillment_route = route
        sale.save(update_fields=["fulfillment_route"])
    else:
        route_office_order(office_order, user, fields, note=note)
    office_order.refresh_from_db()
    sale.refresh_from_db()

    outstanding = balance_due(sale)
    from backend.models import Sale

    if sale.accounting_mode == Sale.ACCOUNTING_MODE_AUTOMATIC:
        if not sale.journal_links.exists():
            _create_sale_accounting(sale, outstanding)
        from logic.accounting import approve_sale_accounting_entries

        approve_sale_accounting_entries(sale)

    if has_checks:
        reg_account = _resolve_account(check_registration_account_id, "collection_at_bank")
        dep_account = _resolve_account(check_deposit_account_id, "bank")
        register_sale_checks(sale, reg_account, dep_account, user=user)
        save_user_accounting_preference(
            user,
            registration_account_id=reg_account.id,
            deposit_account_id=dep_account.id,
            save_as_default=save_check_accounts_as_default,
        )

    if sale.paid_amount > 0:
        _apply_purchase_to_customer(
            sale.customer,
            sale.paid_amount,
            sale.sold_at,
            reason="تایید اداری — مبلغ پرداخت‌شده",
            user=user,
            sale=sale,
        )
    return office_order


def _user_display(user):
    if not user:
        return None
    name = user.get_full_name() or user.username
    return name.strip() or user.username


def _append_workflow_note(description, label, reason=""):
    note = (
        f"[برگشت اداری — {label}: {reason.strip()}]"
        if reason and reason.strip()
        else f"[برگشت اداری — {label}]"
    )
    combined = f"{description}\n{note}".strip() if description else note
    return combined[:255]


def get_office_workflow_snapshot(office_order, factory_order=None):
    """وضعیت فعلی کالا، واحد مسئول و امکان برگشت یک مرحله."""
    from backend.models import FactoryOrder, OfficeOrder

    if factory_order is None and office_order.status == OfficeOrder.STATUS_RELEASED:
        factory_order = office_order

    if office_order.status == OfficeOrder.STATUS_PENDING:
        return {
            "workflow_stage": STAGE_BRANCH_APPROVED,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_BRANCH_APPROVED],
            "holder_department": "اداری CRM",
            "holder_name": None,
            "holder_detail": "در انتظار بررسی و تایید اداری",
            "can_rollback": True,
            "rollback_label": "بازگشت به فروشگاه",
            "rollback_action": "to_shop",
        }

    stage = office_order.workflow_stage_id

    if stage == STAGE_IN_WAREHOUSE:
        source = office_order.fulfillment_warehouse or office_order.fulfillment_source_branch
        source_label = source.label if source else "انبار"
        return {
            "workflow_stage": STAGE_IN_WAREHOUSE,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_IN_WAREHOUSE],
            "holder_department": "انبار",
            "holder_name": _user_display(office_order.accounting_approved_by),
            "holder_detail": f"ارسال از {source_label}",
            "can_rollback": True,
            "rollback_label": "بازگشت به صف اداری",
            "rollback_action": "to_office",
        }

    if stage == STAGE_READY_FOR_PICKUP:
        return {
            "workflow_stage": STAGE_READY_FOR_PICKUP,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_READY_FOR_PICKUP],
            "holder_department": "فروشگاه",
            "holder_name": _user_display(office_order.accounting_approved_by),
            "holder_detail": "آماده تحویل حضوری از مغازه",
            "can_rollback": True,
            "rollback_label": "بازگشت به صف اداری",
            "rollback_action": "to_office",
        }

    if stage == STAGE_MERCHANT_ASSIGNED:
        merchant = _user_display(office_order.merchant_user)
        return {
            "workflow_stage": STAGE_MERCHANT_ASSIGNED,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_MERCHANT_ASSIGNED],
            "holder_department": "کارخانه",
            "holder_name": merchant,
            "holder_detail": "فاکتور بازرگان — در صف ساخت" + (f" — همکار: {merchant}" if merchant else ""),
            "can_rollback": True,
            "rollback_label": "بازگشت به صف اداری",
            "rollback_action": "to_office",
        }

    if factory_order is None:
        factory_order = office_order

    stage = factory_order.workflow_stage_id
    if stage == FactoryOrder.WORKFLOW_STAGE_COMPLETED:
        return {
            "workflow_stage": STAGE_COMPLETED,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_COMPLETED],
            "holder_department": "تکمیل‌شده",
            "holder_name": None,
            "holder_detail": "سفارش تحویل شده است",
            "can_rollback": False,
            "rollback_label": None,
            "rollback_action": None,
        }

    if stage == FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED:
        sender = _user_display(factory_order.accounting_approved_by)
        return {
            "workflow_stage": STAGE_ACCOUNTING_APPROVED,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_ACCOUNTING_APPROVED],
            "holder_department": "کارخانه",
            "holder_name": sender,
            "holder_detail": "در صف دریافت کارخانه" + (f" — ارسال: {sender}" if sender else ""),
            "can_rollback": True,
            "rollback_label": "بازگشت به صف اداری",
            "rollback_action": "to_office",
        }

    if stage == FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION:
        receiver = _user_display(factory_order.factory_received_by)
        return {
            "workflow_stage": STAGE_IN_PRODUCTION,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_IN_PRODUCTION],
            "holder_department": "کارخانه",
            "holder_name": receiver,
            "holder_detail": "در حال ساخت" + (f" — مسئول: {receiver}" if receiver else ""),
            "can_rollback": True,
            "rollback_label": "بازگشت به صف دریافت کارخانه",
            "rollback_action": "from_production",
        }

    if stage == FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE:
        ready = bool(factory_order.delivery_ready_at)
        pending = bool(
            factory_order.early_disposition_required and not factory_order.early_ship_allowed_date
        )
        if ready:
            detail = "منتظر تعیین تکلیف اداری" if pending else "آماده تحویل — در انتظار ارسال به باربری"
        else:
            detail = "ساخته شده — منتظر تایید نهایی"
        return {
            "workflow_stage": STAGE_PRODUCTION_DONE,
            "workflow_stage_display": "آماده تحویل" if ready else WORKFLOW_STAGE_LABELS[STAGE_PRODUCTION_DONE],
            "holder_department": "کارخانه",
            "holder_name": _user_display(factory_order.delivery_ready_by or factory_order.factory_received_by),
            "holder_detail": detail,
            "can_rollback": True,
            "rollback_label": "بازگشت به خط ساخت",
            "rollback_action": "from_production_done",
        }

    if stage == FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT:
        receiver = _user_display(factory_order.freight_received_by)
        return {
            "workflow_stage": STAGE_IN_FREIGHT,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_IN_FREIGHT],
            "holder_department": "باربری",
            "holder_name": receiver,
            "holder_detail": "در حال تحویل" + (f" — مسئول: {receiver}" if receiver else ""),
            "can_rollback": True,
            "rollback_label": "بازگشت به آماده باربری",
            "rollback_action": "from_freight",
        }

    return {
        "workflow_stage": stage,
        "workflow_stage_display": WORKFLOW_STAGE_LABELS.get(stage, stage),
        "holder_department": "—",
        "holder_name": None,
        "holder_detail": "—",
        "can_rollback": False,
        "rollback_label": None,
        "rollback_action": None,
    }


@transaction.atomic
def recall_factory_order_to_office(office_order, user, reason=""):
    from backend.models import OfficeOrder, Sale
    from logic.order_queues import as_office_order, transition_order

    allowed = {
        STAGE_ACCOUNTING_APPROVED,
        STAGE_IN_WAREHOUSE,
        STAGE_READY_FOR_PICKUP,
        STAGE_MERCHANT_ASSIGNED,
    }
    if office_order.status != OfficeOrder.STATUS_RELEASED:
        raise ValueError("فقط سفارش‌های ارسال‌شده از اداری قابل بازگردانی هستند.")
    if office_order.workflow_stage_id not in allowed:
        raise ValueError("این سفارش در مرحله‌ای نیست که بتوان آن را به اداری برگرداند.")

    sale = transition_order(
        office_order,
        STAGE_BRANCH_APPROVED,
        user,
        note=reason,
        description=_append_workflow_note(office_order.description, "بازگشت به اداری", reason),
        accounting_approved_at=None,
        accounting_approved_by_id=None,
        factory_released_at=None,
        fulfillment_route=None,
        fulfillment_warehouse_id=None,
        fulfillment_source_branch_id=None,
        merchant_user_id=None,
        order_status=Sale.ORDER_STATUS_PENDING,
    )
    return as_office_order(sale)


@transaction.atomic
def rollback_factory_receive(factory_order, user, reason=""):
    factory_order.refresh_from_db()
    if factory_order.workflow_stage_id != factory_order.WORKFLOW_STAGE_IN_PRODUCTION:
        raise ValueError("این سفارش در مرحله ساخت نیست.")
    from logic.order_queues import as_factory_order, transition_order

    sale = transition_order(
        factory_order,
        STAGE_ACCOUNTING_APPROVED,
        user,
        note=reason,
        description=_append_workflow_note(factory_order.description, "خروج از ساخت", reason),
        factory_received_at=None,
        factory_received_by_id=None,
    )
    return as_factory_order(sale)


@transaction.atomic
def rollback_factory_production_done(factory_order, user, reason=""):
    if factory_order.workflow_stage_id != factory_order.WORKFLOW_STAGE_PRODUCTION_DONE:
        raise ValueError("این سفارش آماده باربری نیست.")
    from logic.materials import restore_materials_for_factory_order
    from logic.order_queues import as_factory_order, transition_order

    restore_materials_for_factory_order(factory_order)
    from logic.early_ship import CLEAR_READY_FIELDS, close_disposition_threads

    close_disposition_threads(factory_order, user)
    sale = transition_order(
        factory_order,
        STAGE_IN_PRODUCTION,
        user,
        note=reason,
        description=_append_workflow_note(factory_order.description, "بازگشت به ساخت", reason),
        production_done_at=None,
        **CLEAR_READY_FIELDS,
    )
    return as_factory_order(sale)


@transaction.atomic
def rollback_factory_freight_receive(factory_order, user, reason=""):
    if factory_order.workflow_stage_id != factory_order.WORKFLOW_STAGE_IN_FREIGHT:
        raise ValueError("این سفارش در مرحله باربری نیست.")
    from logic.order_queues import as_factory_order, transition_order

    sale = transition_order(
        factory_order,
        STAGE_PRODUCTION_DONE,
        user,
        note=reason,
        description=_append_workflow_note(factory_order.description, "خروج از تحویل", reason),
        freight_received_at=None,
        freight_received_by_id=None,
        shipped_early=False,
    )
    return as_factory_order(sale)


@transaction.atomic
def rollback_office_workflow_step(office_order, user, reason=""):
    snapshot = get_office_workflow_snapshot(office_order)
    action = snapshot.get("rollback_action")
    if not snapshot.get("can_rollback") or not action:
        raise ValueError("این سفارش در مرحله‌ای نیست که بتوان آن را برگرداند.")

    if action == "to_shop":
        return reject_office_order(office_order, user, reason=reason)
    if action == "to_office":
        return recall_factory_order_to_office(office_order, user, reason=reason)

    factory = office_order
    if action == "from_production":
        rollback_factory_receive(factory, user, reason=reason)
    elif action == "from_production_done":
        rollback_factory_production_done(factory, user, reason=reason)
    elif action == "from_freight":
        rollback_factory_freight_receive(factory, user, reason=reason)
    else:
        raise ValueError("عملیات برگشت نامعتبر است.")
    return office_order


def _append_office_rejection_note(description, reason=""):
    note = (
        f"[عدم تایید اداری: {reason.strip()}]"
        if reason and reason.strip()
        else "[عدم تایید اداری]"
    )
    combined = f"{description}\n{note}".strip() if description else note
    return combined[:255]


@transaction.atomic
def reject_office_order(office_order, user, reason=""):
    from logic.order_queues import transition_order

    if office_order.status != office_order.STATUS_PENDING:
        raise ValueError("فقط سفارش‌های در انتظار تایید اداری قابل عدم تایید هستند.")

    sale = office_order.source_sale
    if sale.order_status == sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    from backend.models import JournalEntry
    JournalEntry.objects.filter(
        order_links__order=sale,
        status_ref_id=JournalEntry.STATUS_DRAFT,
    ).delete()

    return transition_order(
        sale,
        STAGE_PENDING_BRANCH,
        user,
        note=reason,
        description=_append_office_rejection_note(sale.description, reason),
        office_released_at=None,
        branch_approved_at=None,
        branch_approved_by_id=None,
    )


@transaction.atomic
def receive_factory_order(factory_order, user):
    allowed = {
        factory_order.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        STAGE_MERCHANT_ASSIGNED,
    }
    if factory_order.workflow_stage_id not in allowed:
        raise ValueError("این سفارش هنوز برای کارخانه ارسال نشده است.")
    from logic.order_queues import as_factory_order, transition_order

    sale = transition_order(
        factory_order,
        STAGE_IN_PRODUCTION,
        user,
        factory_received_at=timezone.now(),
        factory_received_by_id=user.pk if user else None,
    )
    from logic.production_line import spawn_workshop_jobs_for_sale

    spawned = spawn_workshop_jobs_for_sale(sale)
    result = as_factory_order(sale)
    result.spawned_workshop_jobs = spawned
    return result


@transaction.atomic
def complete_factory_production(factory_order, user):
    if factory_order.workflow_stage_id != factory_order.WORKFLOW_STAGE_IN_PRODUCTION:
        raise ValueError("این سفارش در مرحله ساخت کارخانه نیست.")
    from logic.materials import deduct_materials_for_factory_order
    from logic.order_queues import as_factory_order, transition_order
    from logic.receive_kinds import destination_stage

    deduct_materials_for_factory_order(factory_order)
    next_stage = destination_stage(getattr(factory_order, "receive_kind", None) or "customer")
    extra = {"production_done_at": timezone.now()}
    if next_stage == STAGE_IN_WAREHOUSE:
        extra["delivery_ready_at"] = timezone.now()
    elif next_stage == STAGE_READY_FOR_PICKUP:
        extra["delivery_ready_at"] = timezone.now()
    sale = transition_order(
        factory_order,
        next_stage,
        user,
        **extra,
    )
    return as_factory_order(sale)


@transaction.atomic
def receive_factory_freight(factory_order, user):
    from logic.early_ship import send_factory_order_to_freight

    return send_factory_order_to_freight(factory_order, user)


@transaction.atomic
def complete_factory_freight(factory_order, user):
    today = timezone.localdate()
    if factory_order.delivery_date != today:
        raise ValueError("فقط سفارش‌های با تاریخ تحویل امروز قابل تکمیل هستند.")
    if factory_order.workflow_stage_id != factory_order.WORKFLOW_STAGE_IN_FREIGHT:
        raise ValueError("این سفارش در مرحله باربری نیست.")
    from logic.order_queues import as_factory_order, transition_order

    sale = transition_order(
        factory_order,
        STAGE_COMPLETED,
        user,
        freight_completed_at=timezone.now(),
    )
    return as_factory_order(sale)


@transaction.atomic
def complete_warehouse_order(sale, user):
    from logic.order_queues import transition_order

    if sale.workflow_stage_id != STAGE_IN_WAREHOUSE:
        raise ValueError("این سفارش در مرحله انبار نیست.")
    return transition_order(
        sale,
        STAGE_COMPLETED,
        user,
        note="تکمیل ارسال انبار",
        warehouse_completed_at=timezone.now(),
    )


@transaction.atomic
def complete_pickup_order(sale, user):
    from logic.order_queues import transition_order

    if sale.workflow_stage_id != STAGE_READY_FOR_PICKUP:
        raise ValueError("این سفارش آماده تحویل حضوری نیست.")
    return transition_order(
        sale,
        STAGE_COMPLETED,
        user,
        note="تحویل حضوری به مشتری",
        pickup_completed_at=timezone.now(),
    )
