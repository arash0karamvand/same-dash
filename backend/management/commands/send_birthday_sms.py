"""ارسال خودکار پیامک تبریک تولد — برای cron یا Task Scheduler."""

from django.core.management.base import BaseCommand

from logic.birthday_sms import build_preview, send_birthday_batch


class Command(BaseCommand):
    help = "ارسال پیامک تبریک تولد مشتریان (طبق ساعت تنظیم‌شده)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="ارسال حتی اگر امروز قبلاً ارسال شده باشد",
        )

    def handle(self, *args, **options):
        preview = build_preview(auto_run=not options["force"])
        if options["force"]:
            result = send_birthday_batch(force=True, scheduled=True)
            self.stdout.write(
                self.style.SUCCESS(
                    f"ارسال اجباری: {result['successful']} موفق، {result['failed']} ناموفق"
                )
            )
            return

        if preview.get("auto_result"):
            r = preview["auto_result"]
            if r.get("already_ran"):
                self.stdout.write("امروز قبلاً ارسال شده است.")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"ارسال خودکار: {r.get('successful', 0)} موفق، {r.get('failed', 0)} ناموفق"
                    )
                )
        elif preview.get("send_due"):
            self.stdout.write("زمان ارسال رسیده — در حال ارسال…")
        else:
            self.stdout.write(
                f"ارسال در ساعت {preview['send_time']} — "
                f"{preview['will_send_count']} مشتری در صف"
            )
