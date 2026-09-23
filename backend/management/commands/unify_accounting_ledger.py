import json
import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from backend.models import (
    Account,
    CostCenter,
    JournalEntry,
    Ledger,
    LedgerMigrationAudit,
)
from logic.accounting_transfer import transfer_factory_document_to_office
from logic.document_issuance import DocumentIssuanceService


def _posted_totals(ledger):
    result = ledger.journal_entries.filter(
        status_ref_id=JournalEntry.STATUS_POSTED
    ).aggregate(debit=Sum("lines__debit"), credit=Sum("lines__credit"))
    return {
        "debit": str(result["debit"] or Decimal(0)),
        "credit": str(result["credit"] or Decimal(0)),
        "journals": ledger.journal_entries.exclude(
            status_ref_id=JournalEntry.STATUS_VOID
        ).count(),
    }


class Command(BaseCommand):
    help = "Dry-run/cutover امن دفتر کارخانه به دفتر قانونی واحد"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm", default="")
        parser.add_argument("--rollback-batch")

    def handle(self, *args, **options):
        if options["rollback_batch"]:
            return self._rollback(options["rollback_batch"])

        office = Ledger.objects.get(code="office")
        factory = Ledger.objects.get(code="factory")
        factory_journals = list(
            factory.journal_entries.exclude(status_ref_id=JournalEntry.STATUS_VOID)
            .prefetch_related("lines__account")
            .order_by("id")
        )
        transferred = [j for j in factory_journals if hasattr(j, "transferred_journal")]
        pending = [j for j in factory_journals if not hasattr(j, "transferred_journal")]
        missing_paths = sorted({
            line.account.path
            for journal in pending
            for line in journal.lines.all()
            if not Account.objects.filter(ledger=office, path=line.account.path).exists()
        })
        report = {
            "mode": "apply" if options["apply"] else "dry-run",
            "office_before": _posted_totals(office),
            "factory_before": _posted_totals(factory),
            "factory_journals": len(factory_journals),
            "already_transferred": len(transferred),
            "to_transfer_as_draft": len(pending),
            "missing_account_paths": missing_paths,
            "factory_cost_centers": factory.cost_centers.count(),
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "Dry-run بود؛ برای اجرا --apply --confirm=UNIFY-OFFICE-FACTORY لازم است."
            ))
            return
        if options["confirm"] != "UNIFY-OFFICE-FACTORY":
            raise CommandError("عبارت تأیید معتبر نیست.")

        batch_id = uuid.uuid4()
        errors = []
        with transaction.atomic():
            self._ensure_accounts(factory, office, batch_id)
            self._ensure_cost_centers(factory, office, batch_id)
            for journal in pending:
                try:
                    result = transfer_factory_document_to_office(
                        document_code=journal.document_code,
                        user=None,
                    )
                    LedgerMigrationAudit.objects.create(
                        batch_id=batch_id,
                        action="transfer_journal",
                        entity_type="JournalEntry",
                        entity_id=str(journal.id),
                        before={
                            "factory_document_code": journal.document_code,
                            "factory_ledger_id": factory.id,
                        },
                        after=result,
                    )
                except Exception as exc:
                    errors.append({"document": journal.document_code, "error": str(exc)})
            if errors:
                raise CommandError(json.dumps(errors, ensure_ascii=False))
            LedgerMigrationAudit.objects.create(
                batch_id=batch_id,
                action="deactivate_ledger",
                entity_type="Ledger",
                entity_id=str(factory.id),
                before={"is_active": factory.is_active},
                after={"is_active": False},
            )
            factory.is_active = False
            factory.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"Cutover ایجاد شد؛ batch={batch_id}. اسناد جدید دفتر کارخانه به‌صورت پیش‌نویس در دفتر واحد هستند."
        ))

    def _ensure_accounts(self, factory, office, batch_id):
        mapping = {}
        for source in factory.accounts.order_by("path"):
            parent = mapping.get(source.parent_id)
            target = Account.objects.filter(ledger=office, path=source.path).first()
            if target is None:
                target = Account.objects.create(
                    ledger=office,
                    parent=parent,
                    slug=self._unique_slug(office, source.slug),
                    code=source.code,
                    name=source.name,
                    account_class=source.account_class,
                    normal_balance=source.normal_balance,
                    sort_order=source.sort_order,
                    legacy_entry_type=source.legacy_entry_type,
                    is_active=source.is_active,
                )
                LedgerMigrationAudit.objects.create(
                    batch_id=batch_id,
                    action="create_account",
                    entity_type="Account",
                    entity_id=str(target.id),
                    before={"factory_account_id": source.id},
                    after={"office_account_id": target.id, "path": target.path},
                )
            mapping[source.id] = target

    @staticmethod
    def _unique_slug(office, slug):
        if not Account.objects.filter(ledger=office, slug=slug).exists():
            return slug
        base = f"{slug}-factory"
        candidate = base
        index = 2
        while Account.objects.filter(ledger=office, slug=candidate).exists():
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def _ensure_cost_centers(self, factory, office, batch_id):
        for source in factory.cost_centers.all():
            target, created = CostCenter.objects.get_or_create(
                ledger=office,
                code=source.code,
                defaults={
                    "branch": source.branch,
                    "name": source.name,
                    "kind": source.kind,
                    "allocation_base": source.allocation_base,
                    "base_quantity": source.base_quantity,
                    "is_active": source.is_active,
                },
            )
            if created:
                LedgerMigrationAudit.objects.create(
                    batch_id=batch_id,
                    action="create_cost_center",
                    entity_type="CostCenter",
                    entity_id=str(target.id),
                    before={"factory_cost_center_id": source.id},
                    after={"office_cost_center_id": target.id},
                )

    def _rollback(self, batch):
        try:
            batch_id = uuid.UUID(str(batch))
        except ValueError as exc:
            raise CommandError("شناسه batch نامعتبر است.") from exc
        audits = LedgerMigrationAudit.objects.filter(batch_id=batch_id).order_by("-id")
        if not audits.exists():
            raise CommandError("batch یافت نشد.")
        service = DocumentIssuanceService()
        with transaction.atomic():
            for audit in audits:
                if audit.action == "transfer_journal":
                    code = (audit.after or {}).get("office_document_code")
                    journal = JournalEntry.objects.filter(
                        ledger__code="office", document_code=code
                    ).first()
                    if journal and journal.status != JournalEntry.STATUS_POSTED:
                        service.retire_draft(journal, reason=f"rollback مهاجرت {batch_id}")
                elif audit.action == "deactivate_ledger":
                    Ledger.objects.filter(pk=audit.entity_id).update(
                        is_active=(audit.before or {}).get("is_active", True)
                    )
            LedgerMigrationAudit.objects.create(
                batch_id=batch_id,
                action="rollback",
                entity_type="Batch",
                entity_id=str(batch_id),
                before={},
                after={"rolled_back": True},
            )
        self.stdout.write(self.style.SUCCESS(f"Rollback batch {batch_id} انجام شد."))
