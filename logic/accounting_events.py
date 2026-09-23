"""درگاه یکتای تبدیل رویدادهای عملیاتی به سند حسابداری.

تمام ثبت‌های خودکار باید ابتدا یک FinancialEvent یکتا بسازند. سند حاصل
پیش‌نویس است و تنها توسط گردش تأیید حسابداری ثبت قطعی می‌شود.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from backend.models import FinancialEvent
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
    event, created = FinancialEvent.objects.select_for_update().get_or_create(
        source_module=identity.source_module,
        source_type=identity.source_type,
        source_key=identity.source_key,
        event_type=identity.event_type,
        defaults={
            "payload": payload or {},
            "payload_hash": digest,
            "occurred_at": occurred_at or timezone.now(),
            "rule_version": rule_version,
        },
    )
    if not created and event.payload_hash != digest:
        raise FinancialEventConflict(
            "رویداد مالی با همین کلید و اطلاعات متفاوت قبلاً ثبت شده است."
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
    sale=None,
    production_order=None,
    inventory_transaction=None,
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
                ledger=OFFICE_LEDGER,
                user=user,
                branch=branch,
                sale=sale,
                production_order=production_order,
                inventory_transaction=inventory_transaction,
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
