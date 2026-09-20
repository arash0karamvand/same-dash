"""نوع دریافت کار کارخانه و ثبت کار اداری."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.models import Branch, Customer, Sale, Warehouse, WorkflowStage
from logic.sale_workflow import STAGE_ACCOUNTING_APPROVED

RECEIVE_KIND_CUSTOMER = Sale.RECEIVE_KIND_CUSTOMER
RECEIVE_KIND_BRANCH_FLOOR = Sale.RECEIVE_KIND_BRANCH_FLOOR
RECEIVE_KIND_WAREHOUSE = Sale.RECEIVE_KIND_WAREHOUSE
RECEIVE_KIND_MERCHANT = Sale.RECEIVE_KIND_MERCHANT
RECEIVE_KIND_REPAIR = Sale.RECEIVE_KIND_REPAIR

RECEIVE_KIND_LABELS = dict(Sale.RECEIVE_KIND_CHOICES)
OFFICE_RECEIVE_KINDS = {
    RECEIVE_KIND_BRANCH_FLOOR,
    RECEIVE_KIND_WAREHOUSE,
    RECEIVE_KIND_MERCHANT,
    RECEIVE_KIND_REPAIR,
}
ALL_RECEIVE_KINDS = {code for code, _ in Sale.RECEIVE_KIND_CHOICES}

DESTINATION_FREIGHT = "freight"
DESTINATION_WAREHOUSE = "warehouse"
DESTINATION_BRANCH = "branch"

DESTINATION_LABELS = {
    DESTINATION_FREIGHT: "باربری",
    DESTINATION_WAREHOUSE: "تحویل انبار",
    DESTINATION_BRANCH: "تحویل شعبه",
}


def normalize_receive_kind(value, *, default=RECEIVE_KIND_CUSTOMER):
    kind = (value or default or "").strip()
    if kind not in ALL_RECEIVE_KINDS:
        raise ValueError("نوع دریافت نامعتبر است.")
    return kind


def clearance_destination(receive_kind):
    if receive_kind == RECEIVE_KIND_WAREHOUSE:
        return DESTINATION_WAREHOUSE
    if receive_kind == RECEIVE_KIND_BRANCH_FLOOR:
        return DESTINATION_BRANCH
    return DESTINATION_FREIGHT


def destination_stage(receive_kind):
    from logic.sale_workflow import (
        STAGE_IN_WAREHOUSE,
        STAGE_PRODUCTION_DONE,
        STAGE_READY_FOR_PICKUP,
    )

    dest = clearance_destination(receive_kind)
    if dest == DESTINATION_WAREHOUSE:
        return STAGE_IN_WAREHOUSE
    if dest == DESTINATION_BRANCH:
        return STAGE_READY_FOR_PICKUP
    return STAGE_PRODUCTION_DONE


def sale_receive_payload(sale):
    kind = sale.receive_kind or RECEIVE_KIND_CUSTOMER
    dest = clearance_destination(kind)
    source = sale.source_invoice
    return {
        "receive_kind": kind,
        "receive_kind_display": RECEIVE_KIND_LABELS.get(kind, kind),
        "contract_party": sale.contract_party or "",
        "source_invoice_id": sale.source_invoice_id,
        "source_invoice_number": source.invoice_number if source else "",
        "clearance_destination": dest,
        "clearance_destination_display": DESTINATION_LABELS.get(dest, dest),
    }


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@transaction.atomic
def create_office_factory_work(user, data):
    """ثبت کار کارخانه از اداری — مستقیم در صف دریافت کارخانه."""
    from logic.branches import branch_labels
    from logic.products import resolve_line_item_from_catalog
    from logic.sellers import effective_sale_branch, get_seller_for_user

    kind = normalize_receive_kind(data.get("receive_kind"), default="")
    if kind not in OFFICE_RECEIVE_KINDS:
        raise ValueError("اداری فقط کف شعبه، انبار، بازرگان یا تعمیر را ثبت می‌کند.")

    contract_party = (data.get("contract_party") or "").strip()
    if kind == RECEIVE_KIND_MERCHANT and not contract_party:
        raise ValueError("برای بازرگان طرف قرارداد را وارد کنید.")

    customer = None
    customer_id = _optional_int(data.get("customer_id"))
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, is_deleted=False).first()
        if not customer:
            raise ValueError("مشتری یافت نشد.")

    source_invoice = None
    source_id = _optional_int(data.get("source_invoice_id"))
    source_number = (data.get("source_invoice_number") or "").strip()
    if source_id:
        source_invoice = Sale.objects.filter(pk=source_id, is_deleted=False).first()
        if not source_invoice:
            raise ValueError("فاکتور مبدأ یافت نشد.")
    elif source_number:
        source_invoice = Sale.objects.filter(invoice_number=source_number, is_deleted=False).first()
        if not source_invoice:
            raise ValueError("فاکتور مبدأ یافت نشد.")

    raw_items = data.get("line_items") or []
    if not raw_items:
        raise ValueError("حداقل یک ردیف محصول لازم است.")
    resolved_items = []
    amount = Decimal(0)
    for item in raw_items:
        payload = dict(item) if isinstance(item, dict) else {}
        payload["require_price"] = False
        resolved = resolve_line_item_from_catalog(payload)
        if not resolved:
            raise ValueError("هر ردیف باید از کاتالوگ محصولات انتخاب شود.")
        resolved_items.append(resolved)
        amount += Decimal(resolved["unit_price"] or 0) * resolved["quantity"]

    labels = branch_labels()
    requested = (data.get("branch") or "").strip()
    if requested and requested in labels:
        branch = requested
    else:
        seller = get_seller_for_user(user)
        branch = effective_sale_branch(user) or (seller.branch_id if seller else "") or "branch_1"
    warehouse = None
    source_branch = None
    if kind == RECEIVE_KIND_WAREHOUSE:
        warehouse_id = _optional_int(data.get("fulfillment_warehouse_id") or data.get("warehouse_id"))
        if warehouse_id:
            warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
        if not warehouse:
            raise ValueError("برای تولید انبار، مقصد انبار را انتخاب کنید.")
    if kind == RECEIVE_KIND_BRANCH_FLOOR:
        branch_code = (data.get("fulfillment_source_branch") or data.get("source_branch") or "").strip()
        if branch_code:
            source_branch = Branch.objects.filter(code=branch_code).first()
        if not source_branch:
            source_branch = Branch.objects.filter(code=branch).first()
        if not source_branch:
            raise ValueError("برای کف شعبه، شعبه مقصد را انتخاب کنید.")

    invoice_number = (data.get("invoice_number") or "").strip() or None
    description = (data.get("description") or "").strip()
    delivery_date = data.get("delivery_date") or None

    sale = Sale.objects.create(
        customer=customer,
        amount=amount,
        discount_type="amount",
        discount_value=Decimal(0),
        discount=Decimal(0),
        final_amount=amount,
        paid_amount=Decimal(0),
        payment_method="cash",
        payment_status="unpaid",
        accounting_mode="automatic",
        invoice_number=invoice_number,
        description=description,
        recorded_by=user,
        branch_id=branch or "branch_1",
        order_kind=Sale.ORDER_KIND_NORMAL,
        order_status=Sale.ORDER_STATUS_CONFIRMED,
        workflow_stage_id=STAGE_ACCOUNTING_APPROVED,
        delivery_date=delivery_date,
        fulfillment_route=Sale.FULFILLMENT_ROUTE_FACTORY,
        fulfillment_warehouse=warehouse,
        fulfillment_source_branch=source_branch,
        receive_kind=kind,
        contract_party=contract_party,
        seat_count=data.get("seat_count") or None,
        source_invoice=source_invoice,
        accounting_approved_at=timezone.now(),
        accounting_approved_by=user,
    )
    from backend.models import OrderTransition, SaleLineItem

    OrderTransition.objects.create(
        order=sale,
        from_stage=None,
        to_stage=WorkflowStage.objects.get(code=STAGE_ACCOUNTING_APPROVED),
        actor=user,
        note="ثبت کار کارخانه از اداری",
    )
    for resolved in resolved_items:
        qty = resolved["quantity"]
        price = Decimal(resolved["unit_price"] or 0)
        SaleLineItem.objects.create(
            sale=sale,
            product=resolved["product"],
            variant=resolved.get("variant"),
            frame=resolved.get("frame"),
            frame_model=resolved.get("frame_model"),
            frame_config=resolved.get("frame_config") or {},
            workset_config=resolved.get("workset_config") or {},
            furniture_workset=resolved.get("furniture_workset"),
            product_name=resolved["product_name"],
            product_model=resolved.get("product_model") or "",
            fabric=resolved.get("fabric") or "",
            color_name=resolved.get("color_name") or "",
            color_hex=resolved.get("color_hex") or "",
            quantity=qty,
            unit_price=price,
            line_total=price * qty,
        )
    return sale
