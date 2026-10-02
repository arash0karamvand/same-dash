"""Resolution and administration of configurable posting-account mappings."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from backend.models import Account, PostingAccountMapping
from logic.dynamic_choices import posting_rules
from logic.ledger import OFFICE_LEDGER


def _ledger_row(ledger):
    return getattr(ledger, "model", ledger)


def validate_postable_account(account, *, ledger):
    ledger_row = _ledger_row(ledger)
    if account.ledger_id != ledger_row.id:
        raise ValueError("حساب نگاشت متعلق به دفتر سند نیست.")
    if not account.is_active:
        raise ValueError("حساب نگاشت غیرفعال است.")
    if not account.is_postable:
        raise ValueError("حساب نگاشت باید حساب برگ و قابل ثبت باشد.")
    return account


def resolve_mapped_account(
    event_key,
    role,
    side,
    *,
    ledger=OFFICE_LEDGER,
    branch=None,
    warehouse=None,
    item_category="",
    effective_date=None,
):
    """Return the most specific active mapping, or ``None`` for legacy fallback."""
    ledger_row = _ledger_row(ledger)
    when = effective_date or timezone.localdate()
    if hasattr(when, "date"):
        when = when.date()
    branch_code = getattr(branch, "pk", None) or getattr(branch, "code", None) or branch
    warehouse_id = getattr(warehouse, "pk", None) or warehouse
    category = str(
        getattr(item_category, "slug", None)
        or getattr(item_category, "code", None)
        or item_category
        or ""
    ).strip().lower()

    candidates = (
        PostingAccountMapping.objects.select_related("account")
        .filter(
            ledger=ledger_row,
            event_key=event_key,
            role=role,
            side=side,
            is_active=True,
            effective_from__lte=when,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=when))
        .filter(Q(branch__isnull=True) | Q(branch_id=branch_code))
        .filter(Q(warehouse__isnull=True) | Q(warehouse_id=warehouse_id))
        .filter(Q(item_category="") | Q(item_category=category))
    )
    ranked = sorted(
        candidates,
        key=lambda row: (
            int(bool(row.branch_id)) + int(bool(row.warehouse_id)) + int(bool(row.item_category)),
            row.priority,
            row.effective_from,
            row.pk,
        ),
        reverse=True,
    )
    if not ranked:
        return None
    return validate_postable_account(ranked[0].account, ledger=ledger_row)


def mapping_to_dict(mapping):
    account = mapping.account
    return {
        "id": mapping.id,
        "ledger_id": mapping.ledger_id,
        "event_key": mapping.event_key,
        "role": mapping.role,
        "side": mapping.side,
        "account_id": mapping.account_id,
        "account": {
            "id": account.id,
            "slug": account.slug,
            "code": account.full_code,
            "name": account.name,
        },
        "branch": mapping.branch_id,
        "warehouse_id": mapping.warehouse_id,
        "item_category": mapping.item_category,
        "effective_from": mapping.effective_from.isoformat(),
        "effective_to": mapping.effective_to.isoformat() if mapping.effective_to else None,
        "is_active": mapping.is_active,
        "priority": mapping.priority,
        "metadata": mapping.metadata,
    }


def _date_value(value, *, required=False):
    if value in (None, ""):
        if required:
            return timezone.localdate()
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("تاریخ نگاشت باید میلادی و به قالب YYYY-MM-DD باشد.") from exc


def save_mapping(data, *, mapping=None, ledger=OFFICE_LEDGER):
    ledger_row = _ledger_row(ledger)
    account_id = data.get("account_id", mapping.account_id if mapping else None)
    try:
        account = Account.objects.get(pk=account_id)
    except (Account.DoesNotExist, TypeError, ValueError) as exc:
        raise ValueError("حساب مقصد یافت نشد.") from exc
    row = mapping or PostingAccountMapping(ledger=ledger_row)
    row.event_key = data.get("event_key", row.event_key)
    row.role = data.get("role", row.role)
    row.side = data.get("side", row.side)
    row.account = account
    row.branch_id = data.get("branch") or None
    row.warehouse_id = data.get("warehouse_id") or None
    row.item_category = data.get("item_category", row.item_category or "")
    row.effective_from = _date_value(
        data.get("effective_from", row.effective_from if mapping else None),
        required=True,
    )
    row.effective_to = _date_value(data.get("effective_to", row.effective_to))
    row.is_active = bool(data.get("is_active", row.is_active))
    row.priority = int(data.get("priority", row.priority or 0))
    row.metadata = data.get("metadata", row.metadata or {}) or {}
    try:
        row.save()
    except ValidationError as exc:
        messages = []
        if hasattr(exc, "message_dict"):
            messages = [message for values in exc.message_dict.values() for message in values]
        raise ValueError("؛ ".join(messages or exc.messages)) from exc
    return row


def mapping_coverage(*, ledger=OFFICE_LEDGER):
    ledger_row = _ledger_row(ledger)
    results = []
    missing = 0
    for event_key, lines in (posting_rules() or {}).items():
        for index, rule in enumerate(lines):
            role = rule.get("role") or rule.get("account_key") or rule.get("slug") or f"line-{index + 1}"
            side = rule.get("side")
            mapped = PostingAccountMapping.objects.filter(
                ledger=ledger_row,
                event_key=event_key,
                role=role,
                side=side,
                is_active=True,
            ).exists()
            fallback_slug = rule.get("slug") or ""
            fallback = bool(
                fallback_slug
                and Account.objects.filter(
                    ledger=ledger_row,
                    slug=fallback_slug,
                    is_active=True,
                    children__isnull=True,
                ).exists()
            )
            external = bool(rule.get("account_key"))
            covered = mapped or fallback or external
            missing += int(not covered)
            results.append(
                {
                    "event_key": event_key,
                    "role": role,
                    "side": side,
                    "mapped": mapped,
                    "fallback_slug": fallback_slug or None,
                    "fallback_available": fallback,
                    "caller_supplied": external,
                    "covered": covered,
                }
            )
    return {"results": results, "missing": missing, "total": len(results)}
