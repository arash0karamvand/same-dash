"""محاسبهٔ شبانهٔ امتیاز RFM مشتریان — برای cron یا Task Scheduler."""

from django.core.management.base import BaseCommand

from logic.rfm import recalculate_all_rfm


class Command(BaseCommand):
    help = "محاسبهٔ امتیاز RFM همهٔ مشتریان و ارسال پیامک بخش‌های فعال"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-sms",
            action="store_true",
            help="فقط امتیاز را به‌روز کن؛ پیامک خودکار نفرست",
        )

    def handle(self, *args, **options):
        result = recalculate_all_rfm(send_actions=not options["skip_sms"])
        self.stdout.write(
            self.style.SUCCESS(
                "RFM: {scored} مشتری، {unmatched} بدون بخش، "
                "{sms_sent} پیامک، {sms_skipped} ردشده، {sms_failed} ناموفق".format(
                    scored=result.get("scored", 0),
                    unmatched=result.get("unmatched", 0),
                    sms_sent=result.get("sms_sent", 0),
                    sms_skipped=result.get("sms_skipped", 0),
                    sms_failed=result.get("sms_failed", 0),
                )
            )
        )
