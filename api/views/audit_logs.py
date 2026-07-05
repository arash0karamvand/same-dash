"""مشاهده لاگ فعالیت‌ها — فقط مدیر سیستم."""

from django.db.models import Q

from api.helpers import api_view, fail, success
from auth.executives import can_view_executive_logs
from auth.permissions import VIEW_AUDIT_LOGS, has_permission
from backend.models import AuditLog


def _log_to_dict(entry):
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


@api_view("GET")
def audit_log_list(request):
    if not has_permission(request.user, VIEW_AUDIT_LOGS):
        return fail("Permission denied", status=403)

    qs = AuditLog.objects.select_related("user").all()
    if not can_view_executive_logs(request.user):
        qs = qs.filter(is_executive_only=False)

    action = (request.GET.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    entity_type = (request.GET.get("entity_type") or "").strip()
    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    search = (request.GET.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(message__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(entity_type__icontains=search)
        )

    total = qs.count()
    offset = max(0, int(request.GET.get("offset") or 0))
    limit = min(max(1, int(request.GET.get("limit") or 200)), 500)
    results = qs[offset : offset + limit]

    return success(
        {
            "results": [_log_to_dict(e) for e in results],
            "total": total,
            "offset": offset,
            "limit": limit,
            "actions": [
                {"value": value, "label": label}
                for value, label in AuditLog.ACTION_CHOICES
            ],
        }
    )
