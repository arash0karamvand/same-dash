import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F, Q, Sum

from backend.models import (
    DeliveryDocument,
    FinancialEvent,
    GoodsReceipt,
    InventoryConsumption,
    InventoryCostLayer,
    JournalEntry,
    JournalLine,
    Ledger,
    ProductionEvent,
    ReconciliationQueue,
)
from logic.feature_flags import rollout_status


class Command(BaseCommand):
    help = "کنترل invariantهای دفتر کل، اسناد و رویدادهای مالی"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--allow-factory", action="store_true")

    def handle(self, *args, **options):
        posted = JournalEntry.objects.filter(status_ref_id=JournalEntry.STATUS_POSTED)
        line_totals = {
            row["journal_id"]: row
            for row in JournalLine.objects.filter(journal__in=posted)
            .values("journal_id")
            .annotate(debit=Sum("debit"), credit=Sum("credit"), count=Count("id"))
        }
        unbalanced = []
        total_mismatch = []
        too_few_lines = []
        for journal in posted.only("id", "document_code", "debit_total", "credit_total"):
            totals = line_totals.get(journal.id) or {
                "debit": Decimal(0),
                "credit": Decimal(0),
                "count": 0,
            }
            debit = totals["debit"] or Decimal(0)
            credit = totals["credit"] or Decimal(0)
            if debit != credit or debit <= 0:
                unbalanced.append(journal.document_code)
            if debit != journal.debit_total or credit != journal.credit_total:
                total_mismatch.append(journal.document_code)
            if totals["count"] < 2:
                too_few_lines.append(journal.document_code)

        cross_ledger = JournalLine.objects.exclude(
            journal__ledger_id=F("account__ledger_id")
        ).count()
        duplicate_events = (
            FinancialEvent.objects.values(
                "source_module", "source_type", "source_key", "event_type"
            )
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .count()
        )
        drafted_without_journal = FinancialEvent.objects.filter(
            status__in=[FinancialEvent.STATUS_DRAFTED, FinancialEvent.STATUS_POSTED],
            journal__isnull=True,
        ).count()
        journals_with_multiple_live_events = (
            FinancialEvent.objects.exclude(status=FinancialEvent.STATUS_VOID)
            .exclude(journal__isnull=True)
            .values("journal_id")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .count()
        )
        event_journal_status_mismatch = FinancialEvent.objects.filter(
            Q(status=FinancialEvent.STATUS_POSTED)
            & ~Q(journal__status_ref_id=JournalEntry.STATUS_POSTED)
            | Q(status=FinancialEvent.STATUS_DRAFTED)
            & Q(journal__status_ref_id=JournalEntry.STATUS_POSTED)
        ).count()
        factory = Ledger.objects.filter(code="factory").first()
        factory_live = (
            JournalEntry.objects.filter(ledger=factory)
            .exclude(status_ref_id=JournalEntry.STATUS_VOID)
            .count()
            if factory
            else 0
        )
        global_totals = JournalLine.objects.filter(
            journal__status_ref_id=JournalEntry.STATUS_POSTED
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        debit = global_totals["debit"] or Decimal(0)
        credit = global_totals["credit"] or Decimal(0)
        flags = rollout_status()
        open_reconciliation = (
            ReconciliationQueue.objects.filter(status=ReconciliationQueue.STATUS_OPEN).count()
            if any(flags.values()) else 0
        )
        delivery_missing_events = (
            DeliveryDocument.objects.filter(status=DeliveryDocument.STATUS_POSTED)
            .filter(
                Q(sale_event__isnull=True)
                | Q(cogs_event__isnull=True)
                | Q(sale_event__journal__isnull=True)
                | Q(cogs_event__journal__isnull=True)
            )
            .count()
            if flags["unified_delivery"] else 0
        )
        receipt_missing_accounting = (
            GoodsReceipt.objects.filter(status=GoodsReceipt.STATUS_APPROVED)
            .filter(
                Q(accounting_event__isnull=True)
                | Q(accounting_event__journal__isnull=True)
                | Q(lines__inventory_move__isnull=True)
            )
            .distinct()
            .count()
            if flags["procurement"] else 0
        )
        production_trace_missing = (
            ProductionEvent.objects.filter(
                event_type__in=[
                    ProductionEvent.TYPE_CONSUMPTION,
                    ProductionEvent.TYPE_EXTRA_CONSUMPTION,
                ]
            )
            .filter(
                Q(consumption__isnull=True)
                | Q(run__bom_version__isnull=True)
            )
            .count()
            if flags["actual_cost_production"] else 0
        )
        lot_balance_mismatch = 0
        allocation_mismatch = 0
        if flags["fulfillment_reservations"] or flags["actual_cost_production"]:
            for layer in InventoryCostLayer.objects.annotate(
                allocated=Sum("allocations__quantity")
            ).only("original_qty", "qty_remaining"):
                if Decimal(layer.qty_remaining or 0) != (
                    Decimal(layer.original_qty or 0) - Decimal(layer.allocated or 0)
                ):
                    lot_balance_mismatch += 1
            for consumption in InventoryConsumption.objects.annotate(
                allocated=Sum("allocations__quantity")
            ).only("quantity"):
                if Decimal(consumption.quantity or 0) != Decimal(consumption.allocated or 0):
                    allocation_mismatch += 1

        result = {
            "ok": True,
            "global_debit": str(debit),
            "global_credit": str(credit),
            "global_difference": str(debit - credit),
            "posted_unbalanced": unbalanced,
            "posted_total_mismatch": total_mismatch,
            "posted_too_few_lines": too_few_lines,
            "cross_ledger_lines": cross_ledger,
            "duplicate_financial_events": duplicate_events,
            "event_status_without_journal": drafted_without_journal,
            "journals_with_multiple_live_events": journals_with_multiple_live_events,
            "event_journal_status_mismatch": event_journal_status_mismatch,
            "factory_live_journals": factory_live,
            "feature_flags": flags,
            "open_reconciliation_items": open_reconciliation,
            "delivery_missing_events": delivery_missing_events,
            "approved_receipts_missing_accounting": receipt_missing_accounting,
            "production_trace_missing": production_trace_missing,
            "lot_balance_mismatch": lot_balance_mismatch,
            "allocation_quantity_mismatch": allocation_mismatch,
        }
        failures = [
            bool(unbalanced),
            bool(total_mismatch),
            bool(too_few_lines),
            cross_ledger > 0,
            duplicate_events > 0,
            drafted_without_journal > 0,
            journals_with_multiple_live_events > 0,
            event_journal_status_mismatch > 0,
            debit != credit,
            factory_live > 0 and not options["allow_factory"],
            open_reconciliation > 0,
            delivery_missing_events > 0,
            receipt_missing_accounting > 0,
            production_trace_missing > 0,
            lot_balance_mismatch > 0,
            allocation_mismatch > 0,
        ]
        result["ok"] = not any(failures)

        text = json.dumps(result, ensure_ascii=False, indent=2)
        if options["as_json"]:
            self.stdout.write(text)
        else:
            self.stdout.write(self.style.SUCCESS(text) if result["ok"] else self.style.WARNING(text))
        if not result["ok"]:
            raise CommandError("کنترل هسته حسابداری ناموفق بود.")
