"""درگاه یکتای تبدیل رویدادهای عملیاتی به سند حسابداری.

تمام ثبت‌های خودکار باید ابتدا یک FinancialEvent یکتا بسازند. سند حاصل
پیش‌نویس است و تنها توسط گردش تأیید حسابداری ثبت قطعی می‌شود.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from backend.models import AccountingSourceReference, FinancialEvent, TransactionSource
from logic.document_issuance import DocumentIssuanceService
from logic.ledger import OFFICE_LEDGER


class FinancialEventConflict(ValueError):
    """همان کلید رویداد با payload متفاوت دوباره دریافت شده است."""


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def payload_digest(payload: dict | None) -> str:
    encoded = json.dumps(
        payload or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_key(source) -> str:
    value = getattr(source, "uuid", None) or getattr(source, "pk", None) or source
    if value is None:
        raise ValueError("کلید مبدأ رویداد مالی الزامی است.")
    return str(value)


def register_source_reference(
    *,
    source_module: str,
    source_type: str,
    source_uuid,
    metadata: dict | None = None,
):
    """Register an FK-free UUID reference for a future accounting domain."""
    try:
        value = UUID(str(source_uuid))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("شناسه مرجع حسابداری باید UUID معتبر باشد.") from exc
    reference, _created = AccountingSourceReference.objects.get_or_create(
        source_type=(source_type or "").strip().lower(),
        source_uuid=value,
        defaults={
            "source_module": (source_module or "").strip().lower(),
            "metadata": metadata or {},
        },
    )
    if reference.source_module != (source_module or "").strip().lower():
        raise FinancialEventConflict("این UUID با ماژول دیگری ثبت شده است.")
    return reference


@dataclass(frozen=True)
class EventIdentity:
    source_module: str
    source_type: str
    source_key: str
    event_type: str


@transaction.atomic
def register_event(
    *,
    source_module: str,
    source_type: str,
    source,
    event_type: str,
    payload: dict | None = None,
    occurred_at: datetime | None = None,
    rule_version: str = "1",
    source_reference: AccountingSourceReference | None = None,
) -> tuple[FinancialEvent, bool]:
    identity = EventIdentity(
        source_module=(source_module or "").strip(),
        source_type=(source_type or "").strip(),
        source_key=source_key(source),
        event_type=(event_type or "").strip(),
    )
    if not all(identity.__dict__.values()):
        raise ValueError("مشخصات کامل رویداد مالی الزامی است.")
    digest = payload_digest(payload)
    lookup = {
        "source_module": identity.source_module,
        "source_type": identity.source_type,
        "source_key": identity.source_key,
        "event_type": identity.event_type,
    }
    try:
        with transaction.atomic():
            event, created = FinancialEvent.objects.select_for_update().get_or_create(
                **lookup,
                defaults={
                    "payload": payload or {},
                    "payload_hash": digest,
                    "occurred_at": occurred_at or timezone.now(),
                    "rule_version": rule_version,
                    "source_reference": source_reference,
                },
            )
    except IntegrityError:
        # MySQL cannot lock a row that does not exist; a concurrent insert can
        # win the unique-key race. Re-read and apply the same conflict checks.
        event = FinancialEvent.objects.select_for_update().get(**lookup)
        created = False
    if not created and event.payload_hash != digest:
        raise FinancialEventConflict(
            "رویداد مالی با همین کلید و اطلاعات متفاوت قبلاً ثبت شده است."
        )
    if not created and (
        event.rule_version != rule_version
        or (
            source_reference is not None
            and event.source_reference_id != source_reference.pk
        )
    ):
        raise FinancialEventConflict(
            "رویداد مالی با همین کلید و نسخه قانون/مرجع متفاوت قبلاً ثبت شده است."
        )
    return event, created


def issue_event_draft(
    event: FinancialEvent,
    *,
    lines: list[dict],
    entry_type: str,
    description: str,
    entry_date=None,
    user=None,
    branch=None,
    ledger=OFFICE_LEDGER,
    sale=None,
    production_order=None,
    inventory_transaction=None,
    source_reference=None,
):
    """برای رویداد یک سند پیش‌نویس یکتا صادر می‌کند."""
    try:
        with transaction.atomic():
            locked = FinancialEvent.objects.select_for_update().select_related("journal").get(pk=event.pk)
            if locked.journal_id:
                return locked.journal
            journal = DocumentIssuanceService().issue(
                lines=lines,
                entry_type=entry_type,
                description=description,
                entry_date=entry_date or locked.occurred_at,
                finalize=False,
                ledger=ledger,
                user=user,
                branch=branch,
                sale=sale,
                production_order=production_order,
                inventory_transaction=inventory_transaction,
            )
            reference = source_reference or locked.source_reference
            if reference is not None:
                TransactionSource.objects.get_or_create(
                    transaction=journal,
                    source_reference=reference,
                )
            locked.journal = journal
            locked.status = FinancialEvent.STATUS_DRAFTED
            locked.error = ""
            locked.save(update_fields=["journal", "status", "error", "updated_at"])
            return journal
    except Exception as exc:
        FinancialEvent.objects.filter(pk=event.pk).update(
            status=FinancialEvent.STATUS_FAILED,
            error=str(exc),
        )
        raise


def issue_through_gateway(
    *,
    source_module: str,
    source_type: str,
    source,
    event_type: str,
    rule_name: str,
    amounts: dict,
    entry_type: str,
    description: str,
    accounts: dict | None = None,
    payload: dict | None = None,
    occurred_at=None,
    ledger=OFFICE_LEDGER,
    branch=None,
    warehouse=None,
    item_category="",
    source_uuid=None,
    source_metadata=None,
    user=None,
    **issuance_links,
):
    """Reusable idempotent automatic-posting gateway for later domain phases."""
    from logic.feature_flags import ACCOUNTING_GATEWAY, require_feature
    from logic.posting import build_journal_lines

    require_feature(ACCOUNTING_GATEWAY)
    reference = None
    uuid_value = source_uuid or getattr(source, "uuid", None)
    if uuid_value:
        reference = register_source_reference(
            source_module=source_module,
            source_type=source_type,
            source_uuid=uuid_value,
            metadata=source_metadata,
        )
    event, created = register_event(
        source_module=source_module,
        source_type=source_type,
        source=source,
        event_type=event_type,
        payload=payload if payload is not None else amounts,
        occurred_at=occurred_at,
        source_reference=reference,
    )
    if event.journal_id:
        return event, event.journal, created
    lines = build_journal_lines(
        rule_name,
        amounts=amounts,
        accounts=accounts,
        description=description,
        ledger=ledger,
        branch=branch,
        warehouse=warehouse,
        item_category=item_category,
        effective_date=occurred_at,
    )
    journal = issue_event_draft(
        event,
        lines=lines,
        entry_type=entry_type,
        description=description,
        entry_date=occurred_at,
        user=user,
        branch=branch,
        ledger=ledger,
        source_reference=reference,
        **issuance_links,
    )
    return event, journal, created


@transaction.atomic
def finalize_event(event: FinancialEvent, *, user=None):
    locked = FinancialEvent.objects.select_for_update().select_related("journal").get(pk=event.pk)
    if not locked.journal_id:
        raise ValidationError("برای رویداد هنوز سند پیش‌نویس صادر نشده است.")
    if locked.status == FinancialEvent.STATUS_POSTED:
        return locked.journal
    journal = DocumentIssuanceService().finalize(locked.journal, user=user)
    locked.status = FinancialEvent.STATUS_POSTED
    locked.error = ""
    locked.save(update_fields=["status", "error", "updated_at"])
    return journal


@transaction.atomic
def reverse_event(event: FinancialEvent, *, reason: str, user=None):
    locked = FinancialEvent.objects.select_for_update().select_related("journal").get(pk=event.pk)
    if not locked.journal_id:
        raise ValidationError("رویداد سند قابل اصلاح ندارد.")
    if locked.journal.status == locked.journal.STATUS_POSTED:
        correction = DocumentIssuanceService().issue_correction(
            locked.journal, reason=reason, user=user
        )
    else:
        correction = DocumentIssuanceService().retire_draft(
            locked.journal, reason=reason, user=user
        )
    locked.status = FinancialEvent.STATUS_VOID
    locked.save(update_fields=["status", "updated_at"])
    return correction
