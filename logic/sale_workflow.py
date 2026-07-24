"""گردش کار سفارش — جداول جدا: فروشگاه → اداری → کارخانه."""

from django.db import transaction
from django.utils import timezone

STAGE_PENDING_BRANCH = "pending_branch"
STAGE_BRANCH_APPROVED = "branch_approved"
STAGE_ACCOUNTING_APPROVED = "accounting_approved"
STAGE_IN_PRODUCTION = "in_production"
STAGE_PRODUCTION_DONE = "production_done"
STAGE_IN_FREIGHT = "in_freight"
STAGE_COMPLETED = "completed"

WORKFLOW_STAGE_LABELS = {
    STAGE_PENDING_BRANCH: "صف فروشگاه",
    STAGE_BRANCH_APPROVED: "صف اداری",
    STAGE_ACCOUNTING_APPROVED: "ارسال به کارخانه",
    STAGE_IN_PRODUCTION: "در حال ساخت",
    STAGE_PRODUCTION_DONE: "آماده باربری",
    STAGE_IN_FREIGHT: "در باربری",
    STAGE_COMPLETED: "تکمیل شده",
}

BRANCH_MASK_STAGES = {
    STAGE_BRANCH_APPROVED,
    STAGE_ACCOUNTING_APPROVED,
    STAGE_IN_PRODUCTION,
    STAGE_PRODUCTION_DONE,
    STAGE_IN_FREIGHT,
    STAGE_COMPLETED,
}


def uses_workflow_on_create(user):
    """همه سفارش‌های ثبت‌شده تا تایید سرپرست/مدیر در صف فروشگاه می‌مانند."""
    return user is not None and getattr(user, "is_authenticated", False)


def auto_approve_branch_on_create(user):
    """همه سفارش‌ها تا تایید سرپرست معلق می‌مانند."""
    return False


def is_workflow_sale(sale):
    return sale.workflow_stage != STAGE_COMPLETED or sale.order_status == sale.ORDER_STATUS_PENDING


@transaction.atomic
def approve_sale_branch(sale, user):
    from backend.models import Sale
    from logic.order_queues import create_office_order_from_sale

    if sale.workflow_stage != STAGE_PENDING_BRANCH:
        raise ValueError("این سفارش در مرحله تایید سرپرست شعبه نیست.")
    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")
    if sale.transferred_to_office_at:
        raise ValueError("این سفارش قبلاً به اداری ارسال شده است.")

    create_office_order_from_sale(sale, user)
    return sale


@transaction.atomic
def approve_office_order(office_order, user):
    from logic.order_queues import create_factory_order_from_office
    from logic.sales import _apply_purchase_to_customer, _create_sale_accounting, balance_due

    if office_order.status != office_order.STATUS_PENDING:
        raise ValueError("این سفارش در مرحله تایید اداری نیست.")

    sale = office_order.source_sale
    if sale.order_status == sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    create_factory_order_from_office(office_order, user)

    outstanding = balance_due(sale)
    if not sale.accounting_entries.exists():
        _create_sale_accounting(sale, outstanding)
        if sale.paid_amount > 0:
            _apply_purchase_to_customer(
                sale.customer,
                sale.paid_amount,
                sale.sold_at,
                reason="تایید اداری — مبلغ پرداخت‌شده",
                user=user,
            )
    from logic.accounting import approve_sale_accounting_entries

    approve_sale_accounting_entries(sale)
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

    if factory_order is None:
        try:
            factory_order = office_order.factory_order
        except FactoryOrder.DoesNotExist:
            factory_order = None
    if factory_order and factory_order.is_deleted:
        factory_order = None

    if office_order.status == OfficeOrder.STATUS_PENDING:
        return {
            "workflow_stage": STAGE_BRANCH_APPROVED,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_BRANCH_APPROVED],
            "holder_department": "اداری",
            "holder_name": None,
            "holder_detail": "در انتظار بررسی و تایید اداری",
            "can_rollback": True,
            "rollback_label": "بازگشت به فروشگاه",
            "rollback_action": "to_shop",
        }

    if not factory_order:
        return {
            "workflow_stage": STAGE_BRANCH_APPROVED,
            "workflow_stage_display": "ارسال‌شده — بدون رکورد کارخانه",
            "holder_department": "—",
            "holder_name": None,
            "holder_detail": "—",
            "can_rollback": False,
            "rollback_label": None,
            "rollback_action": None,
        }

    stage = factory_order.workflow_stage
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
        return {
            "workflow_stage": STAGE_PRODUCTION_DONE,
            "workflow_stage_display": WORKFLOW_STAGE_LABELS[STAGE_PRODUCTION_DONE],
            "holder_department": "باربری",
            "holder_name": _user_display(factory_order.factory_received_by),
            "holder_detail": "آماده تحویل در باربری",
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
    from backend.models import FactoryOrder, OfficeOrder

    if office_order.status != OfficeOrder.STATUS_RELEASED:
        raise ValueError("فقط سفارش‌های ارسال‌شده به کارخانه قابل بازگردانی به اداری هستند.")
    try:
        factory = office_order.factory_order
    except FactoryOrder.DoesNotExist:
        raise ValueError("رکورد کارخانه یافت نشد.")
    if factory.is_deleted:
        raise ValueError("رکورد کارخانه یافت نشد.")
    if factory.workflow_stage != FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED:
        raise ValueError("فقط سفارش‌های در صف دریافت کارخانه قابل بازگردانی به اداری هستند.")

    factory.soft_delete()
    office_order.status = OfficeOrder.STATUS_PENDING
    office_order.accounting_approved_at = None
    office_order.accounting_approved_by = None
    office_order.save(
        update_fields=["status", "accounting_approved_at", "accounting_approved_by_id"]
    )

    sale = office_order.source_sale
    sale.description = _append_workflow_note(sale.description, "بازگشت به اداری", reason)
    sale.workflow_stage = sale.WORKFLOW_STAGE_COMPLETED
    sale.accounting_approved_at = None
    sale.accounting_approved_by = None
    sale.factory_released_at = None
    sale.save(
        update_fields=[
            "description",
            "workflow_stage",
            "accounting_approved_at",
            "accounting_approved_by_id",
            "factory_released_at",
        ]
    )
    return office_order


@transaction.atomic
def rollback_factory_receive(factory_order, user, reason=""):
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_IN_PRODUCTION:
        raise ValueError("این سفارش در مرحله ساخت نیست.")
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_ACCOUNTING_APPROVED
    factory_order.factory_received_at = None
    factory_order.factory_received_by = None
    factory_order.save(
        update_fields=["workflow_stage", "factory_received_at", "factory_received_by_id"]
    )

    sale = factory_order.source_sale
    sale.description = _append_workflow_note(sale.description, "خروج از ساخت", reason)
    sale.workflow_stage = STAGE_ACCOUNTING_APPROVED
    sale.factory_received_at = None
    sale.factory_received_by = None
    sale.save(
        update_fields=[
            "description",
            "workflow_stage",
            "factory_received_at",
            "factory_received_by_id",
        ]
    )
    return factory_order


@transaction.atomic
def rollback_factory_production_done(factory_order, user, reason=""):
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_PRODUCTION_DONE:
        raise ValueError("این سفارش آماده باربری نیست.")
    from logic.materials import restore_materials_for_factory_order

    restore_materials_for_factory_order(factory_order)
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_IN_PRODUCTION
    factory_order.production_done_at = None
    factory_order.save(update_fields=["workflow_stage", "production_done_at"])

    sale = factory_order.source_sale
    sale.description = _append_workflow_note(sale.description, "بازگشت به ساخت", reason)
    sale.workflow_stage = STAGE_IN_PRODUCTION
    sale.production_done_at = None
    sale.save(update_fields=["description", "workflow_stage", "production_done_at"])
    return factory_order


@transaction.atomic
def rollback_factory_freight_receive(factory_order, user, reason=""):
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_IN_FREIGHT:
        raise ValueError("این سفارش در مرحله باربری نیست.")
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_PRODUCTION_DONE
    factory_order.freight_received_at = None
    factory_order.freight_received_by = None
    factory_order.save(
        update_fields=["workflow_stage", "freight_received_at", "freight_received_by_id"]
    )

    sale = factory_order.source_sale
    sale.description = _append_workflow_note(sale.description, "خروج از تحویل", reason)
    sale.workflow_stage = STAGE_PRODUCTION_DONE
    sale.freight_received_at = None
    sale.freight_received_by = None
    sale.save(
        update_fields=[
            "description",
            "workflow_stage",
            "freight_received_at",
            "freight_received_by_id",
        ]
    )
    return factory_order


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

    factory = office_order.factory_order
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
    from backend.models import OfficeOrderInstallment

    if office_order.status != office_order.STATUS_PENDING:
        raise ValueError("فقط سفارش‌های در انتظار تایید اداری قابل عدم تایید هستند.")

    sale = office_order.source_sale
    if sale.order_status == sale.ORDER_STATUS_CANCELLED:
        raise ValueError("سفارش لغو شده است.")

    for inst in office_order.installments.filter(is_deleted=False):
        inst.soft_delete()
    office_order.soft_delete()

    sale.description = _append_office_rejection_note(sale.description, reason)
    sale.transferred_to_office_at = None
    sale.office_released_at = None
    sale.branch_approved_at = None
    sale.branch_approved_by = None
    sale.workflow_stage = STAGE_PENDING_BRANCH
    sale.save(
        update_fields=[
            "description",
            "transferred_to_office_at",
            "office_released_at",
            "branch_approved_at",
            "branch_approved_by_id",
            "workflow_stage",
        ]
    )
    return sale


@transaction.atomic
def receive_factory_order(factory_order, user):
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_ACCOUNTING_APPROVED:
        raise ValueError("این سفارش هنوز برای کارخانه ارسال نشده است.")
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_IN_PRODUCTION
    factory_order.factory_received_at = timezone.now()
    factory_order.factory_received_by = user
    factory_order.save(
        update_fields=["workflow_stage", "factory_received_at", "factory_received_by_id"]
    )

    sale = factory_order.source_sale
    sale.workflow_stage = STAGE_IN_PRODUCTION
    sale.factory_received_at = factory_order.factory_received_at
    sale.factory_received_by = user
    sale.save(
        update_fields=["workflow_stage", "factory_received_at", "factory_received_by_id"]
    )
    return factory_order


@transaction.atomic
def complete_factory_production(factory_order, user):
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_IN_PRODUCTION:
        raise ValueError("این سفارش در مرحله ساخت کارخانه نیست.")
    from logic.materials import deduct_materials_for_factory_order

    deduct_materials_for_factory_order(factory_order)
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_PRODUCTION_DONE
    factory_order.production_done_at = timezone.now()
    factory_order.save(update_fields=["workflow_stage", "production_done_at"])

    sale = factory_order.source_sale
    sale.workflow_stage = STAGE_PRODUCTION_DONE
    sale.production_done_at = factory_order.production_done_at
    sale.save(update_fields=["workflow_stage", "production_done_at"])
    return factory_order


@transaction.atomic
def receive_factory_freight(factory_order, user):
    today = timezone.localdate()
    if factory_order.delivery_date != today:
        raise ValueError("فقط سفارش‌های با تاریخ تحویل امروز قابل دریافت هستند.")
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_PRODUCTION_DONE:
        raise ValueError("این سفارش هنوز آماده باربری نیست.")
    from logic.materials import deduct_materials_for_factory_order

    deduct_materials_for_factory_order(factory_order)
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_IN_FREIGHT
    factory_order.freight_received_at = timezone.now()
    factory_order.freight_received_by = user
    factory_order.save(
        update_fields=["workflow_stage", "freight_received_at", "freight_received_by_id"]
    )

    sale = factory_order.source_sale
    sale.workflow_stage = STAGE_IN_FREIGHT
    sale.freight_received_at = factory_order.freight_received_at
    sale.freight_received_by = user
    sale.save(
        update_fields=["workflow_stage", "freight_received_at", "freight_received_by_id"]
    )
    return factory_order


@transaction.atomic
def complete_factory_freight(factory_order, user):
    today = timezone.localdate()
    if factory_order.delivery_date != today:
        raise ValueError("فقط سفارش‌های با تاریخ تحویل امروز قابل تکمیل هستند.")
    if factory_order.workflow_stage != factory_order.WORKFLOW_STAGE_IN_FREIGHT:
        raise ValueError("این سفارش در مرحله باربری نیست.")
    factory_order.workflow_stage = factory_order.WORKFLOW_STAGE_COMPLETED
    factory_order.freight_completed_at = timezone.now()
    factory_order.save(update_fields=["workflow_stage", "freight_completed_at"])

    sale = factory_order.source_sale
    sale.workflow_stage = STAGE_COMPLETED
    sale.freight_completed_at = factory_order.freight_completed_at
    sale.save(update_fields=["workflow_stage", "freight_completed_at"])
    return factory_order
