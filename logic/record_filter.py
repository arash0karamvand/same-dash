"""فیلتر عمومی رکوردها — مدل، نوع، تاریخ، نام، بازه مبلغ."""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from api.filters import parse_date
from backend.models import (
    AccountingEntry,
    AuditLog,
    Customer,
    OfficeOrder,
    Sale,
)


def _parse_amount(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _choices_to_options(choices):
    return [{"value": v, "label": l} for v, l in choices]


OFFICE_FILTER_MODEL_KEYS = frozenset({"office_order", "customer", "sale"})

ACCOUNTING_FILTER_MODEL_KEYS = frozenset({"accounting_entry"})


def filter_catalog(scope=None):
    models = [
            {
                "key": "sale",
                "label": "فروش",
                "date_field_label": "تاریخ فروش",
                "name_label": "نام مشتری / فاکتور",
                "amount_label": "مبلغ نهایی",
                "type_fields": [
                    {
                        "key": "order_kind",
                        "label": "نوع سفارش",
                        "choices": _choices_to_options(Sale.ORDER_KIND_CHOICES),
                    },
                    {
                        "key": "payment_method",
                        "label": "روش پرداخت",
                        "choices": _choices_to_options(Sale.PAYMENT_METHOD_CHOICES),
                    },
                    {
                        "key": "payment_status",
                        "label": "وضعیت پرداخت",
                        "choices": _choices_to_options(Sale.PAYMENT_STATUS_CHOICES),
                    },
                    {
                        "key": "workflow_stage",
                        "label": "مرحله گردش کار",
                        "choices": _choices_to_options(Sale.WORKFLOW_STAGE_CHOICES),
                    },
                ],
            },
            {
                "key": "customer",
                "label": "مشتری",
                "date_field_label": "تاریخ عضویت",
                "name_label": "نام / موبایل",
                "amount_label": "مجموع خرید یا موجودی کیف",
                "amount_fields": [
                    {"key": "total_purchases", "label": "مجموع خرید"},
                    {"key": "wallet_balance", "label": "موجودی کیف پول"},
                ],
                "type_fields": [],
            },
            {
                "key": "office_order",
                "label": "سفارش اداری",
                "date_field_label": "تاریخ ثبت",
                "name_label": "نام مشتری / فاکتور",
                "amount_label": "مبلغ نهایی",
                "type_fields": [
                    {
                        "key": "order_kind",
                        "label": "نوع سفارش",
                        "choices": _choices_to_options(Sale.ORDER_KIND_CHOICES),
                    },
                    {
                        "key": "status",
                        "label": "وضعیت اداری",
                        "choices": _choices_to_options(OfficeOrder.STATUS_CHOICES),
                    },
                ],
            },
            {
                "key": "accounting_entry",
                "label": "سند حسابداری",
                "date_field_label": "تاریخ سند",
                "name_label": "شرح / کد سند",
                "amount_label": "مبلغ سند",
                "type_fields": [
                    {
                        "key": "entry_type",
                        "label": "نوع سند",
                        "choices": _choices_to_options(AccountingEntry.ENTRY_TYPE_CHOICES),
                    },
                ],
            },
            {
                "key": "audit_log",
                "label": "لاگ فعالیت",
                "date_field_label": "زمان",
                "name_label": "شرح / کاربر / موجودیت",
                "amount_label": None,
                "type_fields": [
                    {
                        "key": "action",
                        "label": "نوع عملیات",
                        "choices": _choices_to_options(AuditLog.ACTION_CHOICES),
                    },
                ],
            },
        ]
    scope_key = (scope or "").strip().lower()
    if scope_key == "office":
        models = [m for m in models if m["key"] in OFFICE_FILTER_MODEL_KEYS]
    elif scope_key == "accounting":
        models = [m for m in models if m["key"] in ACCOUNTING_FILTER_MODEL_KEYS]
    return {"models": models, "scope": scope_key or None}


def _apply_date_range(qs, field_name, date_from, date_to):
    if not date_from and not date_to:
        return qs
    field = qs.model._meta.get_field(field_name)
    is_date_only = field.get_internal_type() == "DateField"
    if date_from:
        if is_date_only:
            qs = qs.filter(**{f"{field_name}__gte": date_from})
        else:
            start = timezone.make_aware(datetime.combine(date_from, time.min))
            qs = qs.filter(**{f"{field_name}__gte": start})
    if date_to:
        if is_date_only:
            qs = qs.filter(**{f"{field_name}__lte": date_to})
        else:
            end = timezone.make_aware(datetime.combine(date_to, time.max))
            qs = qs.filter(**{f"{field_name}__lte": end})
    return qs


def _apply_amount_range(qs, field_name, amount_min, amount_max):
    if amount_min is not None:
        qs = qs.filter(**{f"{field_name}__gte": amount_min})
    if amount_max is not None:
        qs = qs.filter(**{f"{field_name}__lte": amount_max})
    return qs


def _serialize_sale(row):
    return {
        "id": row.id,
        "title": row.customer.full_name if row.customer_id else "—",
        "subtitle": row.invoice_number or "",
        "type_display": row.get_order_kind_display(),
        "amount": int(row.final_amount),
        "date": row.sold_at.isoformat() if row.sold_at else None,
    }


def _serialize_customer(row):
    return {
        "id": row.id,
        "title": row.full_name,
        "subtitle": row.phone,
        "type_display": row.level.name if row.level_id else "—",
        "amount": int(row.total_purchases),
        "date": row.joined_at.isoformat() if row.joined_at else None,
    }


def _serialize_office_order(row):
    return {
        "id": row.id,
        "title": row.customer.full_name if row.customer_id else "—",
        "subtitle": row.invoice_number or "",
        "type_display": row.get_status_display(),
        "amount": int(row.final_amount),
        "date": row.sold_at.isoformat() if row.sold_at else None,
    }


def _serialize_accounting_entry(row):
    return {
        "id": row.id,
        "title": row.description or row.document_code or f"سند #{row.id}",
        "subtitle": row.get_entry_type_display(),
        "type_display": row.get_entry_type_display(),
        "amount": int(row.amount),
        "date": row.entry_date.isoformat() if row.entry_date else None,
    }


def _serialize_audit_log(row):
    user = row.user
    name = (user.get_full_name() or user.username) if user else "—"
    return {
        "id": row.id,
        "title": row.message,
        "subtitle": name,
        "type_display": row.get_action_display(),
        "amount": None,
        "date": row.created_at.isoformat() if row.created_at else None,
    }


def query_filtered_records(params, *, include_executive_logs=False):
    model_key = (params.get("model") or "").strip()
    if not model_key:
        raise ValueError("مدل را انتخاب کنید.")

    date_from = parse_date(params.get("date_from"))
    date_to = parse_date(params.get("date_to"))
    type_field = (params.get("type_field") or "").strip()
    type_value = (params.get("type") or params.get("type_value") or "").strip()
    name = (params.get("name") or params.get("search") or "").strip()
    amount_min = _parse_amount(params.get("amount_min"))
    amount_max = _parse_amount(params.get("amount_max"))
    amount_field = (params.get("amount_field") or "").strip()

    offset = max(0, int(params.get("offset") or 0))
    limit = min(max(1, int(params.get("limit") or 100)), 500)

    if model_key == "sale":
        qs = Sale.objects.filter(is_deleted=False).select_related("customer")
        qs = _apply_date_range(qs, "sold_at", date_from, date_to)
        if type_field and type_value:
            qs = qs.filter(**{type_field: type_value})
        if name:
            qs = qs.filter(
                Q(customer__full_name__icontains=name)
                | Q(invoice_number__icontains=name)
                | Q(customer__phone__icontains=name)
            )
        amt_field = amount_field if amount_field in ("final_amount", "paid_amount", "amount") else "final_amount"
        qs = _apply_amount_range(qs, amt_field, amount_min, amount_max)
        total = qs.count()
        rows = qs.order_by("-sold_at")[offset : offset + limit]
        results = [_serialize_sale(r) for r in rows]

    elif model_key == "customer":
        qs = Customer.objects.filter(is_deleted=False).select_related("level")
        qs = _apply_date_range(qs, "joined_at", date_from, date_to)
        if name:
            qs = qs.filter(
                Q(full_name__icontains=name)
                | Q(phone__icontains=name)
                | Q(membership_code__icontains=name)
            )
        amt_field = amount_field if amount_field in ("total_purchases", "wallet_balance") else "total_purchases"
        qs = _apply_amount_range(qs, amt_field, amount_min, amount_max)
        total = qs.count()
        rows = qs.order_by("-joined_at")[offset : offset + limit]
        results = [_serialize_customer(r) for r in rows]

    elif model_key == "office_order":
        qs = OfficeOrder.objects.filter(is_deleted=False).select_related("customer")
        qs = _apply_date_range(qs, "sold_at", date_from, date_to)
        if type_field and type_value:
            qs = qs.filter(**{type_field: type_value})
        if name:
            qs = qs.filter(
                Q(customer__full_name__icontains=name)
                | Q(invoice_number__icontains=name)
            )
        qs = _apply_amount_range(qs, "final_amount", amount_min, amount_max)
        total = qs.count()
        rows = qs.order_by("-created_at")[offset : offset + limit]
        results = [_serialize_office_order(r) for r in rows]

    elif model_key == "accounting_entry":
        qs = AccountingEntry.objects.all()
        qs = _apply_date_range(qs, "entry_date", date_from, date_to)
        if type_field and type_value:
            qs = qs.filter(**{type_field: type_value})
        elif type_value:
            qs = qs.filter(entry_type=type_value)
        if name:
            qs = qs.filter(
                Q(description__icontains=name)
                | Q(document_code__icontains=name)
                | Q(detailed_account__icontains=name)
            )
        qs = _apply_amount_range(qs, "amount", amount_min, amount_max)
        total = qs.count()
        rows = qs.order_by("-entry_date")[offset : offset + limit]
        results = [_serialize_accounting_entry(r) for r in rows]

    elif model_key == "audit_log":
        qs = AuditLog.objects.select_related("user").all()
        if not include_executive_logs:
            qs = qs.filter(is_executive_only=False)
        qs = _apply_date_range(qs, "created_at", date_from, date_to)
        if type_field and type_value:
            qs = qs.filter(**{type_field: type_value})
        elif type_value:
            qs = qs.filter(action=type_value)
        if name:
            qs = qs.filter(
                Q(message__icontains=name)
                | Q(entity_type__icontains=name)
                | Q(user__username__icontains=name)
                | Q(user__first_name__icontains=name)
                | Q(user__last_name__icontains=name)
            )
        total = qs.count()
        rows = qs.order_by("-created_at")[offset : offset + limit]
        results = [_serialize_audit_log(r) for r in rows]

    else:
        raise ValueError("مدل نامعتبر است.")

    catalog = {m["key"]: m for m in filter_catalog()["models"]}
    model_meta = catalog.get(model_key, {})

    return {
        "model": model_key,
        "model_label": model_meta.get("label", model_key),
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": results,
        "filters_applied": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "type_field": type_field or None,
            "type": type_value or None,
            "name": name or None,
            "amount_min": int(amount_min) if amount_min is not None else None,
            "amount_max": int(amount_max) if amount_max is not None else None,
            "amount_field": amount_field or None,
        },
    }
