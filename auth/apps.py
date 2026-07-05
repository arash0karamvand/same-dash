from django.apps import AppConfig


class AuthConfig(AppConfig):
    """اپ احراز هویت پروژه — label جدا از django.contrib.auth."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "auth"
    label = "accounts"

    def ready(self):
        from auth.signals import connect_signals

        connect_signals()
