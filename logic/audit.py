"""ثبت و فهرست لاگ فعالیت‌ها."""

from django.db.models import Q

from backend.models import AuditLog


def log_action(
    user,
    action,
    message,
    *,
    entity_type="",
    entity_id="",
    details=None,
    is_executive_only=False,
):
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        entity_type=entity_type or "",
        entity_id=str(entity_id) if entity_id else "",
        message=message,
        details=details or {},
        is_executive_only=is_executive_only,
    )


def audit_log_to_dict(entry):
    user = entry.user
    return {
        "id": entry.id,
        "user_name": (user.get_full_name() or user.username) if user else "—",
        "username": user.username if user else "",
        "action": entry.action,
        "action_display": entry.get_action_display(),
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "message": entry.message,
        "details": entry.details,
        "is_executive_only": entry.is_executive_only,
        "created_at": entry.created_at.isoformat(),
    }


def list_audit_logs(params, *, include_executive=False):
    qs = AuditLog.objects.select_related("user").all()
    if not include_executive:
        qs = qs.filter(is_executive_only=False)

    action = (params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    entity_type = (params.get("entity_type") or "").strip()
    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(message__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(entity_type__icontains=search)
        )

    total = qs.count()
    offset = max(0, int(params.get("offset") or 0))
    limit = min(max(1, int(params.get("limit") or 200)), 500)
    results = qs[offset : offset + limit]

    return {
        "results": [audit_log_to_dict(e) for e in results],
        "total": total,
        "offset": offset,
        "limit": limit,
        "actions": [
            {"value": value, "label": label}
            for value, label in AuditLog.ACTION_CHOICES
        ],
    }
