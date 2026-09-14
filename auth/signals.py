"""همگام‌سازی نقش superuser و ایجاد گروه‌های نقش."""

from django.contrib.auth import get_user_model
from django.apps import apps
from django.db.models.signals import post_migrate, post_save

from auth import roles

_user_model = get_user_model()
_connected = False


def _ensure_role_groups(**kwargs):
    roles.ensure_roles()


def _sync_superuser_role(sender, instance, **kwargs):
    if not instance.is_superuser:
        return
    roles.ensure_roles()
    if roles.get_user_role(instance) != roles.ADMIN:
        roles.assign_role(instance, roles.ADMIN)


def connect_signals():
    global _connected
    if _connected:
        return
    # post_migrate is emitted once per installed app. Running the same role
    # seeding transaction for every sender can deadlock on MySQL/MariaDB.
    post_migrate.connect(
        _ensure_role_groups,
        sender=apps.get_app_config("backend"),
        dispatch_uid="accounts_ensure_roles",
    )
    post_save.connect(_sync_superuser_role, sender=_user_model, dispatch_uid="accounts_sync_superuser")
    _connected = True
