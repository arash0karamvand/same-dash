"""سرویس CRM: ذخیره، import، export، همگام با Sale."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q

from backend.models import CrmWorkbookRow, Sale
from logic.crm_workbook_io import assign_sort_orders, export_workbook_xlsx, read_uploaded_workbook
from logic.crm_workbook_schema import CRM_COLUMNS, CRM_SHEETS, INVOICE_COLUMN, schema_payload

logger = logging.getLogger(__name__)


def get_schema():
    return schema_payload()


def list_sheet_rows(sheet: str, *, search: str = "", limit: int = 500, offset: int = 0):
    if sheet not in CRM_SHEETS:
        raise ValueError("تب نامعتبر")
    qs = CrmWorkbookRow.objects.filter(sheet=sheet).order_by("sort_order", "id")
    if search.strip():
        qs = qs.filter(
            Q(invoice_ref__icontains=search.strip())
            | Q(data__icontains=search.strip())
        )
    total = qs.count()
    rows = list(qs[offset : offset + limit])
    return {
        "sheet": sheet,
        "label": CRM_SHEETS[sheet],
        "columns": CRM_COLUMNS[sheet],
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": [
            {
                "id": r.id,
                "invoice_ref": r.invoice_ref,
                "sort_order": r.sort_order,
                "data": r.data,
                "source": r.source,
                "sale_id": r.sale_id,
            }
            for r in rows
        ],
    }


def _resolve_sale(invoice_ref: str) -> Sale | None:
    if not invoice_ref:
        return None
    inv = str(invoice_ref).strip()
    sale = Sale.objects.filter(invoice_number=inv).first()
    if sale:
        return sale
    if inv.isdigit():
        return Sale.objects.filter(pk=int(inv)).first()
    return None


@transaction.atomic
def upsert_row(*, sheet: str, data: dict, row_id: int | None, user, source: str = CrmWorkbookRow.SOURCE_MANUAL):
    if sheet not in CRM_SHEETS:
        raise ValueError("تب نامعتبر")
    cols = CRM_COLUMNS[sheet]
    payload = {c: data.get(c) for c in cols}
    inv_col = INVOICE_COLUMN[sheet]
    invoice_ref = str(payload.get(inv_col) or "").strip()

    if row_id:
        try:
            row = CrmWorkbookRow.objects.select_for_update().get(pk=row_id, sheet=sheet)
        except CrmWorkbookRow.DoesNotExist as exc:
            raise ValueError("ردیف یافت نشد") from exc
        row.data = payload
        row.invoice_ref = invoice_ref
        row.source = source
        row.updated_by = user
        row.sale = _resolve_sale(invoice_ref)
        row.save()
        return row

    sort_order = 0
    if invoice_ref:
        existing = CrmWorkbookRow.objects.filter(sheet=sheet, invoice_ref=invoice_ref).order_by("-sort_order").first()
        if existing and sheet == "financial":
            sort_order = existing.sort_order + 1
        elif existing and sheet != "financial":
            existing.data = payload
            existing.source = source
            existing.updated_by = user
            existing.sale = _resolve_sale(invoice_ref)
            existing.save()
            return existing

    row = CrmWorkbookRow.objects.create(
        sheet=sheet,
        invoice_ref=invoice_ref,
        sort_order=sort_order,
        data=payload,
        source=source,
        updated_by=user,
        sale=_resolve_sale(invoice_ref),
    )
    return row


@transaction.atomic
def delete_row(row_id: int, *, sheet: str | None = None):
    qs = CrmWorkbookRow.objects.filter(pk=row_id)
    if sheet:
        qs = qs.filter(sheet=sheet)
    deleted, _ = qs.delete()
    if not deleted:
        raise ValueError("ردیف یافت نشد")


@transaction.atomic
def import_workbook(upload, user, *, password: str | None = None, replace: bool = True):
    parsed = read_uploaded_workbook(upload, password=password)
    stats = {"sheets": {}, "total_rows": 0}

    for sheet_key, rows in parsed.items():
        if replace:
            CrmWorkbookRow.objects.filter(sheet=sheet_key).delete()
        created = 0
        for invoice_ref, sort_order, data in assign_sort_orders(sheet_key, rows):
            sale = _resolve_sale(invoice_ref)
            CrmWorkbookRow.objects.update_or_create(
                sheet=sheet_key,
                invoice_ref=invoice_ref,
                sort_order=sort_order,
                defaults={
                    "data": data,
                    "source": CrmWorkbookRow.SOURCE_EXCEL,
                    "updated_by": user,
                    "sale": sale,
                },
            )
            created += 1
        stats["sheets"][sheet_key] = created
        stats["total_rows"] += created

    return stats


def export_all_rows() -> bytes:
    rows_by_sheet = {k: [] for k in CRM_SHEETS}
    for row in CrmWorkbookRow.objects.order_by("sheet", "sort_order", "id"):
        rows_by_sheet[row.sheet].append(row.data)
    return export_workbook_xlsx(rows_by_sheet)


def _delivery_label(sale: Sale) -> str:
    if sale.order_status == Sale.ORDER_STATUS_CANCELLED:
        return "کنسل شده"
    if sale.workflow_stage_id == Sale.WORKFLOW_STAGE_COMPLETED:
        return "تحویل شده"
    return "تحویل نشده"


@transaction.atomic
def sync_customers_from_sales(user, *, limit: int = 5000):
    """تب مشتریان را از فاکتورهای سیستم پر/به‌روز می‌کند (ورود دوم علاوه بر اکسل)."""
    sheet = "customers"
    cols = CRM_COLUMNS[sheet]
    created = updated = 0

    qs = (
        Sale.objects.select_related("customer", "seller")
        .order_by("-sold_at")[:limit]
    )

    for sale in qs:
        inv = sale.invoice_number or str(sale.pk)
        customer_name = sale.customer.full_name if sale.customer else (sale.contract_party or "")
        balance = sale.final_amount - sale.paid_amount
        data = {c: None for c in cols}
        data["شماره فاکتور"] = inv
        data["نام مشتری"] = customer_name
        data[" تاریخ ثبت سفارش"] = sale.sold_at.strftime("%Y/%m/%d") if sale.sold_at else None
        data["تاریخ تحویل"] = sale.delivery_date.isoformat() if sale.delivery_date else None
        data["مبلغ فاکتور پیش از تخفیف"] = float(sale.amount)
        data["تخفیف"] = float(sale.discount)
        data["مبلغ پس از تخفیف"] = float(sale.final_amount)
        data["مانده حساب"] = float(balance)
        data["وضعیت تحویل"] = _delivery_label(sale)
        data["فروشنده"] = sale.seller.full_name if sale.seller else None

        row, is_new = CrmWorkbookRow.objects.update_or_create(
            sheet=sheet,
            invoice_ref=str(inv),
            sort_order=0,
            defaults={
                "data": data,
                "source": CrmWorkbookRow.SOURCE_SALE_SYNC,
                "updated_by": user,
                "sale": sale,
            },
        )
        if is_new:
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "sheet": sheet}
