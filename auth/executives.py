"""مدیران ارشد و دسترسی لاگ اختصاصی."""

EXECUTIVE_MANAGERS = {
    "sina": "سینا اقتداری",
    "gholamreza": "غلامرضا اقتداری",
    "sepehr": "سپهر اقتداری",
}

# فقط این کاربر لاگ‌های executive-only را می‌بیند
EXECUTIVE_LOG_VIEWER_USERNAME = "gholamreza"


def is_executive_manager(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.username in EXECUTIVE_MANAGERS


def can_view_executive_logs(user):
    if not user or not user.is_authenticated:
        return False
    from auth.roles import ADMIN, get_user_role

    if get_user_role(user) == ADMIN or user.is_superuser:
        return True
    return user.username == EXECUTIVE_LOG_VIEWER_USERNAME
