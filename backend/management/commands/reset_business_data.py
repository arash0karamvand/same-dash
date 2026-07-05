"""پاک‌سازی داده‌های عملیاتی — کاربران مدیر سیستم حفظ می‌شوند."""

from django.core.management.base import BaseCommand

from logic.reset_data import reset_business_data


class Command(BaseCommand):
    help = "Reset all business data; keep system admin users"

    def handle(self, *args, **options):
        counts = reset_business_data()
        self.stdout.write(self.style.SUCCESS("Business data reset complete."))
        for key, value in counts.items():
            self.stdout.write(f"  {key}: {value}")
