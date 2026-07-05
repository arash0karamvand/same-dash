"""پیکربندی اپلیکیشن اصلی پروژه.

تمام مدل‌های دامنه (مشتری، فروش، سطح، باشگاه، پیامک) داخل همین اپ تعریف
می‌شوند تا هستهٔ دیتابیس در یک محل متمرکز باشد.
"""

from django.apps import AppConfig


class BackendConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend"
    verbose_name = "هسته سیستم (مشتریان و فروش)"
