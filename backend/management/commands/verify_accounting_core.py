import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F, Q, Sum

from backend.models import FinancialEvent, JournalEntry, JournalLine, Ledger


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
        ]
        result["ok"] = not any(failures)

        text = json.dumps(result, ensure_ascii=False, indent=2)
        if options["as_json"]:
            self.stdout.write(text)
        else:
            self.stdout.write(self.style.SUCCESS(text) if result["ok"] else self.style.WARNING(text))
        if not result["ok"]:
            raise CommandError("کنترل هسته حسابداری ناموفق بود.")
