"""ارسال خودکار یادآوری‌های دوره‌ای باشگاه."""

from django.core.management.base import BaseCommand

from logic.reminder_sms import run_due_campaigns


class Command(BaseCommand):
    help = "اجرای کمپین‌های یادآوری دوره‌ای که سررسید شده‌اند"

    def handle(self, *args, **options):
        results = run_due_campaigns()
        if not results:
            self.stdout.write("هیچ کمپین سررسیدی یافت نشد.")
            return
        for item in results:
            self.stdout.write(
                f"کمپین {item.get('campaign_id')}: "
                f"{item.get('successful', 0)} موفق، {item.get('failed', 0)} ناموفق"
            )
