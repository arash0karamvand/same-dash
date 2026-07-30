"""انتقال سفارش بین جداول فروشگاه، اداری و کارخانه."""

from django.db import transaction
from django.utils import timezone

from backend.models import (
    FactoryOrder,
    FactoryOrderLineItem,
    OfficeOrder,
    OfficeOrderInstallment,
    OfficeOrderLineItem,
    Sale,
)


def _copy_sale_fields(sale):
    return {
        "customer": sale.customer,
        "amount": sale.amount,
        "discount_type": sale.discount_type,
        "discount_value": sale.discount_value,
        "discount": sale.discount,
        "final_amount": sale.final_amount,
        "paid_amount": sale.paid_amount,
        "sold_at": sale.sold_at,
        "invoice_number": sale.invoice_number,
        "description": sale.description,
        "payment_status": sale.payment_status,
        "payment_method": sale.payment_method,
        "order_kind": sale.order_kind,
        "order_status": sale.order_status,
        "delivery_date": sale.delivery_date,
        "branch": sale.branch or "",
        "recorded_by": sale.recorded_by,
        "seller": sale.seller,
        "accounting_mode": sale.accounting_mode,
    }


def _copy_sale_lines_to_office(office, sale):
    office.line_items.all().delete()
    for line in sale.line_items.all():
        OfficeOrderLineItem.objects.create(
            office_order=office,
            product=line.product,
            variant=line.variant,
            product_name=line.product_name,
            product_model=line.product_model,
            fabric=line.fabric,
            color_name=line.color_name,
            color_hex=line.color_hex,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_total=line.line_total,
        )


def _copy_sale_installments_to_office(office, sale):
    OfficeOrderInstallment.all_objects.filter(office_order=office).delete()
    for inst in sale.installments.filter(is_deleted=False):
        OfficeOrderInstallment.objects.create(
            office_order=office,
            amount=inst.amount,
            due_date=inst.due_date,
            payment_method=inst.payment_method,
            check_number=inst.check_number,
            bank_name=inst.bank_name,
            status=inst.status,
            paid_at=inst.paid_at,
            notes=inst.notes,
        )


@transaction.atomic
def create_office_order_from_sale(sale, user):
    if getattr(sale, "transferred_to_office_at", None):
        raise ValueError("این سفارش قبلاً به اداری ارسال شده است.")
    if OfficeOrder.objects.filter(source_sale=sale).exists():
        raise ValueError("رکورد اداری این سفارش از قبل وجود دارد.")

    now = timezone.now()
    archived = OfficeOrder.all_objects.filter(source_sale=sale, is_deleted=True).first()
    if archived:
        archived.restore()
        for field, value in _copy_sale_fields(sale).items():
            setattr(archived, field, value)
        archived.branch_approved_at = now
        archived.branch_approved_by = user
        archived.accounting_approved_at = None
        archived.accounting_approved_by = None
        archived.status = OfficeOrder.STATUS_PENDING
        archived.save()
        _copy_sale_lines_to_office(archived, sale)
        _copy_sale_installments_to_office(archived, sale)
        office = archived
    else:
        office = OfficeOrder.objects.create(
            source_sale=sale,
            branch_approved_at=now,
            branch_approved_by=user,
            status=OfficeOrder.STATUS_PENDING,
            **_copy_sale_fields(sale),
        )
        _copy_sale_lines_to_office(office, sale)
        _copy_sale_installments_to_office(office, sale)

    sale.transferred_to_office_at = now
    sale.branch_approved_at = now
    sale.branch_approved_by = user
    sale.office_released_at = now
    sale.workflow_stage = Sale.WORKFLOW_STAGE_COMPLETED
    sale.save(
        update_fields=[
            "transferred_to_office_at",
            "branch_approved_at",
            "branch_approved_by_id",
            "office_released_at",
            "workflow_stage",
        ]
    )
    from logic.sales import ensure_draft_sale_accounting

    ensure_draft_sale_accounting(sale)
    return office


@transaction.atomic
def create_factory_order_from_office(office, user):
    if office.status != OfficeOrder.STATUS_PENDING:
        raise ValueError("این سفارش در صف اداری نیست.")
    if hasattr(office, "factory_order") and office.factory_order_id:
        raise ValueError("رکورد کارخانه این سفارش از قبل وجود دارد.")

    sale = office.source_sale
    now = timezone.now()
    factory = FactoryOrder.objects.create(
        source_office_order=office,
        source_sale=sale,
        customer=office.customer,
        invoice_number=office.invoice_number,
        description=office.description,
        delivery_date=office.delivery_date,
        branch=office.branch,
        order_kind=office.order_kind,
        workflow_stage=FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        accounting_approved_at=now,
        accounting_approved_by=user,
    )

    for line in office.line_items.all():
        FactoryOrderLineItem.objects.create(
            factory_order=factory,
            product=line.product,
            variant=line.variant,
            product_name=line.product_name,
            product_model=line.product_model,
            fabric=line.fabric,
            color_name=line.color_name,
            color_hex=line.color_hex,
            quantity=line.quantity,
        )

    office.status = OfficeOrder.STATUS_RELEASED
    office.accounting_approved_at = now
    office.accounting_approved_by = user
    office.save(
        update_fields=[
            "status",
            "accounting_approved_at",
            "accounting_approved_by_id",
        ]
    )

    sale.workflow_stage = Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED
    sale.accounting_approved_at = now
    sale.accounting_approved_by = user
    sale.factory_released_at = now
    sale.order_status = Sale.ORDER_STATUS_CONFIRMED
    sale.save(
        update_fields=[
            "workflow_stage",
            "accounting_approved_at",
            "accounting_approved_by_id",
            "factory_released_at",
            "order_status",
        ]
    )
    return factory


def sync_workflow_orders_from_sale(sale):
    """همگام‌سازی رونوشت اداری و کارخانه با تغییرات فاکتور."""
    if getattr(sale, "is_deleted", False):
        return

    office = OfficeOrder.objects.filter(source_sale=sale).first()
    if office:
        for field, value in _copy_sale_fields(sale).items():
            setattr(office, field, value)
        office.save()

        office.line_items.all().delete()
        for line in sale.line_items.all():
            OfficeOrderLineItem.objects.create(
                office_order=office,
                product=line.product,
                variant=line.variant,
                product_name=line.product_name,
                product_model=line.product_model,
                fabric=line.fabric,
                color_name=line.color_name,
                color_hex=line.color_hex,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )

        office.installments.all().delete()
        for inst in sale.installments.filter(is_deleted=False):
            OfficeOrderInstallment.objects.create(
                office_order=office,
                amount=inst.amount,
                due_date=inst.due_date,
                payment_method=inst.payment_method,
                check_number=inst.check_number,
                bank_name=inst.bank_name,
                status=inst.status,
                paid_at=inst.paid_at,
                notes=inst.notes,
            )

    for factory in FactoryOrder.objects.filter(source_sale=sale):
        factory.line_items.all().delete()
        for line in sale.line_items.all():
            FactoryOrderLineItem.objects.create(
                factory_order=factory,
                product=line.product,
                variant=line.variant,
                product_name=line.product_name,
                product_model=line.product_model,
                fabric=line.fabric,
                color_name=line.color_name,
                color_hex=line.color_hex,
                quantity=line.quantity,
            )
        FactoryOrder.objects.filter(pk=factory.pk).update(
            invoice_number=sale.invoice_number,
            description=sale.description,
            delivery_date=sale.delivery_date,
            branch=sale.branch or "",
        )


@transaction.atomic
def soft_delete_workflow_orders_for_sale(sale):
    """حذف نرم سفارش‌های اداری و کارخانه مرتبط با فاکتور."""
    office = OfficeOrder.all_objects.filter(source_sale=sale).first()
    if office and not office.is_deleted:
        for inst in OfficeOrderInstallment.all_objects.filter(office_order=office):
            if not inst.is_deleted:
                inst.soft_delete()
        office.soft_delete()

    for factory in FactoryOrder.all_objects.filter(source_sale=sale):
        if not factory.is_deleted:
            factory.soft_delete()


def migrate_sale_to_office_if_needed(sale):
    """برای داده‌های قدیمی — انتقال به جدول اداری بدون کاربر."""
    if sale.transferred_to_office_at or OfficeOrder.objects.filter(source_sale=sale).exists():
        return None
    if sale.workflow_stage not in {
        Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
        Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        Sale.WORKFLOW_STAGE_IN_PRODUCTION,
        Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
        Sale.WORKFLOW_STAGE_IN_FREIGHT,
        Sale.WORKFLOW_STAGE_COMPLETED,
    }:
        return None
    if not sale.office_released_at and sale.workflow_stage == Sale.WORKFLOW_STAGE_PENDING_BRANCH:
        return None

    office = OfficeOrder.objects.create(
        source_sale=sale,
        branch_approved_at=sale.branch_approved_at,
        branch_approved_by=sale.branch_approved_by,
        status=OfficeOrder.STATUS_PENDING
        if sale.workflow_stage == Sale.WORKFLOW_STAGE_BRANCH_APPROVED
        else OfficeOrder.STATUS_RELEASED,
        accounting_approved_at=sale.accounting_approved_at,
        accounting_approved_by=sale.accounting_approved_by,
        **_copy_sale_fields(sale),
    )
    for line in sale.line_items.all():
        OfficeOrderLineItem.objects.create(
            office_order=office,
            product=line.product,
            variant=line.variant,
            product_name=line.product_name,
            product_model=line.product_model,
            fabric=line.fabric,
            color_name=line.color_name,
            color_hex=line.color_hex,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_total=line.line_total,
        )
    for inst in sale.installments.filter(is_deleted=False):
        OfficeOrderInstallment.objects.create(
            office_order=office,
            amount=inst.amount,
            due_date=inst.due_date,
            payment_method=inst.payment_method,
            check_number=inst.check_number,
            bank_name=inst.bank_name,
            status=inst.status,
            paid_at=inst.paid_at,
            notes=inst.notes,
        )
    if not sale.transferred_to_office_at:
        sale.transferred_to_office_at = sale.office_released_at or sale.branch_approved_at or timezone.now()
        sale.save(update_fields=["transferred_to_office_at"])
    return office


def migrate_office_to_factory_if_needed(office):
    """برای داده‌های قدیمی — انتقال به جدول کارخانه."""
    if hasattr(office, "factory_order") and FactoryOrder.objects.filter(source_office_order=office).exists():
        return None
    sale = office.source_sale
    if sale.workflow_stage not in {
        Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        Sale.WORKFLOW_STAGE_IN_PRODUCTION,
        Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
        Sale.WORKFLOW_STAGE_IN_FREIGHT,
    }:
        return None
    if not sale.factory_released_at:
        return None

    stage_map = {
        Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED: FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        Sale.WORKFLOW_STAGE_IN_PRODUCTION: FactoryOrder.WORKFLOW_STAGE_IN_PRODUCTION,
        Sale.WORKFLOW_STAGE_PRODUCTION_DONE: FactoryOrder.WORKFLOW_STAGE_PRODUCTION_DONE,
        Sale.WORKFLOW_STAGE_IN_FREIGHT: FactoryOrder.WORKFLOW_STAGE_IN_FREIGHT,
    }
    factory = FactoryOrder.objects.create(
        source_office_order=office,
        source_sale=sale,
        customer=office.customer,
        invoice_number=office.invoice_number,
        description=office.description,
        delivery_date=office.delivery_date,
        branch=office.branch,
        order_kind=office.order_kind,
        workflow_stage=stage_map.get(sale.workflow_stage, FactoryOrder.WORKFLOW_STAGE_ACCOUNTING_APPROVED),
        accounting_approved_at=sale.accounting_approved_at,
        accounting_approved_by=sale.accounting_approved_by,
        factory_received_at=sale.factory_received_at,
        factory_received_by=sale.factory_received_by,
        production_done_at=sale.production_done_at,
        freight_received_at=sale.freight_received_at,
        freight_received_by=sale.freight_received_by,
        freight_completed_at=sale.freight_completed_at,
    )
    for line in office.line_items.all():
        FactoryOrderLineItem.objects.create(
            factory_order=factory,
            product=line.product,
            variant=line.variant,
            product_name=line.product_name,
            product_model=line.product_model,
            fabric=line.fabric,
            color_name=line.color_name,
            color_hex=line.color_hex,
            quantity=line.quantity,
        )
    if office.status == OfficeOrder.STATUS_PENDING:
        office.status = OfficeOrder.STATUS_RELEASED
        office.save(update_fields=["status"])
    return factory
