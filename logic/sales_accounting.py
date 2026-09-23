"""اتصال تایید نهایی فاکتور فروش به هسته اسناد حسابداری."""

from decimal import Decimal
import logging

from django.db import transaction

from backend.models import JournalEntry, JournalOrderLink, OrderStatus, Sale
from logic.accounting_events import issue_event_draft, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.document_issuance import DocumentIssuanceService
from logic.ledger import LEGAL_LEDGER

logger = logging.getLogger(__name__)

NOT_ISSUED = "not_issued"
NOT_ISSUED_LABEL = "سند صادر نشده"
_UNLOADED = object()


def _money(value):
    return str(int(Decimal(value or 0)))


def _ensure_final_status():
    OrderStatus.objects.update_or_create(
        code=Sale.ORDER_STATUS_FINAL,
        defaults={"label": "تایید نهایی", "sort_order": 3, "is_active": True},
    )


def _live_sale_journal(sale):
    return (
        JournalEntry.objects.filter(
            order_links__order=sale,
            entry_type_ref_id="sale",
        )
        .exclude(status_ref_id=JournalEntry.STATUS_VOID)
        .select_related("ledger", "status_ref", "entry_type_ref")
        .order_by("-id")
        .first()
    )


def _issue_sale_journal(sale, user):
    """سند فروش از قانون ثبت هسته.

    فروش نسیه: بدهکار حساب‌های دریافتنی (۱۳۱۰) و بستانکار درآمد فروش (۷۲۴۰).
    بخش نقد فاکتور به حساب دریافت همان روش پرداخت بدهکار می‌شود تا سند تراز بماند.
    """
    from logic.accounting_accounts import get_account, payment_account_for_sale
    from logic.materials import compute_product_material_cost
    from logic.sales import balance_due

    final_amount = Decimal(sale.final_amount or 0)
    if final_amount <= 0:
        raise ValueError("مبلغ فاکتور برای صدور سند باید بزرگ‌تر از صفر باشد.")

    party = sale.customer.full_name if sale.customer_id else "بدون مشتری"
    invoice = sale.invoice_number or sale.pk
    description = f"تایید نهایی فاکتور {invoice} — {party}"
    vat_amount = Decimal(sale.vat_amount or 0)
    net_revenue = final_amount - vat_amount
    outstanding = balance_due(sale)
    paid = Decimal(sale.paid_amount or 0)
    lines = []
    if outstanding > 0:
        lines.append({
            "account": get_account(ACCOUNT_SLUGS.RECEIVABLES, ledger=LEGAL_LEDGER),
            "debit": outstanding,
            "credit": 0,
            "description": description,
        })
    if paid > 0:
        lines.append({
            "account": payment_account_for_sale(sale, ledger=LEGAL_LEDGER),
            "debit": paid,
            "credit": 0,
            "description": description,
        })
    lines.append({
        "account": get_account(ACCOUNT_SLUGS.PRODUCT_SALES, ledger=LEGAL_LEDGER),
        "debit": 0,
        "credit": net_revenue,
        "description": description,
    })
    if vat_amount > 0:
        lines.append({
            "account": get_account(ACCOUNT_SLUGS.VAT_PAYABLE, ledger=LEGAL_LEDGER),
            "debit": 0,
            "credit": vat_amount,
            "description": f"مالیات فروش فاکتور {invoice}",
        })

    cogs = Decimal(0)
    for item in sale.line_items.select_related("product").all():
        if item.product_id:
            cogs += compute_product_material_cost(item.product) * Decimal(item.quantity or 0)
    cogs = cogs.quantize(Decimal("1"))
    if cogs > 0:
        lines.extend([
            {
                "account": get_account(ACCOUNT_SLUGS.COGS, ledger=LEGAL_LEDGER),
                "debit": cogs,
                "credit": 0,
                "description": f"بهای تمام‌شده فاکتور {invoice}",
            },
            {
                "account": get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=LEGAL_LEDGER),
                "debit": 0,
                "credit": cogs,
                "description": f"خروج کالای ساخته‌شده فاکتور {invoice}",
            },
        ])

    event, _created = register_event(
        source_module="sales",
        source_type="Sale",
        source=sale,
        event_type="sale_finalized",
        payload={
            "invoice": str(invoice),
            "final_amount": str(final_amount),
            "vat_amount": str(vat_amount),
            "cogs": str(cogs),
        },
        occurred_at=sale.sold_at,
    )
    journal = issue_event_draft(
        event,
        lines=lines,
        entry_type="sale",
        description=description,
        entry_date=sale.sold_at,
        user=user,
        sale=sale,
        branch=sale.branch,
    )
    logger.info("سند فروش %s برای فاکتور %s صادر شد", journal.document_code, invoice)
    return journal


def journal_line_to_dict(line):
    debit = Decimal(line.debit or 0)
    credit = Decimal(line.credit or 0)
    return {
        "line_number": line.line_number,
        "account_id": line.account_id,
        "account_slug": line.account.slug,
        "account_code": line.account.code,
        "account_name": line.account.name,
        "side": "debit" if debit > 0 else "credit",
        "debit": _money(debit),
        "credit": _money(credit),
        "description": line.description or "",
    }


def journal_to_dict(journal, relation_type):
    journal = (
        JournalEntry.objects.select_related("ledger", "status_ref", "entry_type_ref")
        .prefetch_related("lines__account")
        .get(pk=journal.pk)
    )
    return {
        "id": journal.id,
        "document_number": journal.document_number,
        "document_code": journal.document_code,
        "description": journal.description or "",
        "entry_date": journal.entry_date.isoformat(),
        "entry_type": journal.entry_type,
        "entry_type_label": journal.get_entry_type_display(),
        "status": journal.status,
        "status_label": journal.get_status_display(),
        "ledger_code": journal.ledger.code,
        "ledger_label": journal.ledger.name,
        "relation_type": relation_type,
        "lines": [journal_line_to_dict(line) for line in journal.lines.all()],
    }


def accounting_document_summary(sale):
    journal = getattr(sale, "_accounting_journal", _UNLOADED)
    if journal is _UNLOADED:
        journal = _live_sale_journal(sale)
    if journal is None:
        return {
            "status": NOT_ISSUED,
            "status_label": NOT_ISSUED_LABEL,
            "journal_id": None,
            "document_code": None,
            "document_number": None,
        }
    return {
        "status": journal.status,
        "status_label": journal.get_status_display(),
        "journal_id": journal.id,
        "document_code": journal.document_code,
        "document_number": journal.document_number,
    }


def attach_accounting_journals(sales):
    sales = list(sales)
    ids = [sale.id for sale in sales]
    journals = {}
    if ids:
        links = (
            JournalOrderLink.objects.filter(
                order_id__in=ids,
                journal__entry_type_ref_id="sale",
            )
            .exclude(journal__status_ref_id=JournalEntry.STATUS_VOID)
            .select_related("journal", "journal__status_ref")
            .order_by("journal_id")
        )
        for link in links:
            journals[link.order_id] = link.journal
    for sale in sales:
        sale._accounting_journal = journals.get(sale.id)
    return sales


def sale_journals_payload(sale):
    links = (
        JournalOrderLink.objects.filter(order=sale)
        .select_related("journal")
        .order_by("journal__entry_date", "journal_id")
    )
    journals = [journal_to_dict(link.journal, link.relation_type) for link in links]
    issued = any(
        item["entry_type"] == "sale" and item["status"] != JournalEntry.STATUS_VOID
        for item in journals
    )
    return {
        "sale_id": sale.id,
        "invoice_number": sale.invoice_number or "",
        "order_status": sale.order_status,
        "order_status_display": sale.get_order_status_display(),
        "issued": issued,
        "journals": journals,
    }


@transaction.atomic
def finalize_sale_invoice(sale, user):
    """وضعیت فاکتور را به تایید نهایی می‌برد و در صورت نبود سند، آن را صادر می‌کند."""
    from logic.sales import is_order_cancelled, is_pre_invoice_pending

    sale = Sale.objects.select_for_update().select_related("customer", "branch").get(pk=sale.pk)
    if is_order_cancelled(sale):
        raise ValueError("فاکتور لغو شده قابل تایید نهایی نیست.")
    if is_pre_invoice_pending(sale):
        raise ValueError("پیش‌فاکتور تا قبل از تایید، قابل تایید نهایی نیست.")

    journal = _live_sale_journal(sale)
    already_issued = journal is not None
    if journal is None:
        journal = _issue_sale_journal(sale, user)
    elif journal.status != JournalEntry.STATUS_POSTED:
        DocumentIssuanceService().retire_draft(
            journal,
            user=user,
            reason="جایگزینی پیش‌نویس با سند کامل فروش، مالیات و بهای تمام‌شده",
        )
        journal = _issue_sale_journal(sale, user)

    if sale.order_status != Sale.ORDER_STATUS_FINAL:
        _ensure_final_status()
        sale.order_status = Sale.ORDER_STATUS_FINAL
        sale.save(update_fields=["order_status"])
        sale.refresh_from_db()

    customer_name = sale.customer.full_name if sale.customer_id else ""
    return {
        "sale_id": sale.id,
        "invoice_number": sale.invoice_number or "",
        "customer_name": customer_name,
        "order_status": sale.order_status,
        "order_status_display": sale.get_order_status_display(),
        "issued": True,
        "already_issued": already_issued,
        "journal": journal_to_dict(journal, "sale"),
    }
