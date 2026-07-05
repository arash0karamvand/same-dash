"""ثبت لاگ فعالیت‌ها."""

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
