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
    """Legacy sale/VAT/estimated-COGS document for non-phase-6 sales."""
    from logic.accounting_accounts import get_account, payment_account_for_sale
    from logic.materials import compute_product_material_cost
    from logic.sales import balance_due

    final_amount = Decimal(sale.final_amount or 0)
    if final_amount <= 0:
        raise ValueError("مبلغ فاکتور برای صدور سند باید بزرگ‌تر از صفر باشد.")
    invoice = sale.invoice_number or sale.pk
    description = f"تایید نهایی فاکتور {invoice}"
    vat = Decimal(sale.vat_amount or 0)
    lines = []
    outstanding = balance_due(sale)
    paid = Decimal(sale.paid_amount or 0)
    if outstanding:
        lines.append({"account": get_account(ACCOUNT_SLUGS.RECEIVABLES, ledger=LEGAL_LEDGER),
                      "debit": outstanding, "credit": 0, "description": description})
    if paid:
        lines.append({"account": payment_account_for_sale(sale, ledger=LEGAL_LEDGER),
                      "debit": paid, "credit": 0, "description": description})
    lines.append({"account": get_account(ACCOUNT_SLUGS.PRODUCT_SALES, ledger=LEGAL_LEDGER),
                  "debit": 0, "credit": final_amount - vat, "description": description})
    if vat:
        lines.append({"account": get_account(ACCOUNT_SLUGS.VAT_PAYABLE, ledger=LEGAL_LEDGER),
                      "debit": 0, "credit": vat, "description": description})
    cogs = sum(
        (
            compute_product_material_cost(item.product) * Decimal(item.quantity or 0)
            for item in sale.line_items.select_related("product")
            if item.product_id
        ),
        Decimal("0"),
    ).quantize(Decimal("1"))
    if cogs:
        lines.extend([
            {"account": get_account(ACCOUNT_SLUGS.COGS, ledger=LEGAL_LEDGER),
             "debit": cogs, "credit": 0, "description": description},
            {"account": get_account(ACCOUNT_SLUGS.FINISHED_GOODS_INVENTORY, ledger=LEGAL_LEDGER),
             "debit": 0, "credit": cogs, "description": description},
        ])
    event, _ = register_event(
        source_module="sales", source_type="Sale", source=sale,
        event_type="sale_finalized",
        payload={
            "invoice": str(invoice), "final_amount": str(final_amount),
            "vat_amount": str(vat), "cogs": str(cogs),
        },
        occurred_at=sale.sold_at,
    )
    return issue_event_draft(
        event, lines=lines, entry_type="sale", description=description,
        entry_date=sale.sold_at, user=user, sale=sale, branch=sale.branch,
        ledger=LEGAL_LEDGER,
    )


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
    """Finalize through physical delivery and its idempotent revenue event."""
    from logic.delivery import deliver_sale, is_unified_delivery_candidate
    from logic.feature_flags import UNIFIED_DELIVERY, is_enabled
    from logic.sales import is_order_cancelled, is_pre_invoice_pending

    sale = Sale.objects.select_for_update().select_related("customer", "branch").get(pk=sale.pk)
    if is_order_cancelled(sale):
        raise ValueError("فاکتور لغو شده قابل تایید نهایی نیست.")
    if is_pre_invoice_pending(sale):
        raise ValueError("پیش‌فاکتور تا قبل از تایید، قابل تایید نهایی نیست.")

    unified_delivery = (
        is_enabled(UNIFIED_DELIVERY)
        and is_unified_delivery_candidate(sale)
    )
    already_issued = hasattr(sale, "delivery_document") if unified_delivery else bool(_live_sale_journal(sale))
    if unified_delivery:
        delivery = deliver_sale(sale, user=user)
        journal = delivery.sale_event.journal
    else:
        delivery = None
        journal = _live_sale_journal(sale)
        if journal is None:
            journal = _issue_sale_journal(sale, user)
        elif journal.status != JournalEntry.STATUS_POSTED:
            DocumentIssuanceService().retire_draft(
                journal,
                user=user,
                reason="Replaced by complete legacy sale/VAT/COGS draft",
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
        "delivery_uuid": str(delivery.uuid) if delivery else None,
        "actual_cogs": str(delivery.total_actual_cogs) if delivery else None,
        "journal": journal_to_dict(journal, "sale"),
    }
