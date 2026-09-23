"""Management command برای import مشتریان از فایل‌های agents/*.xlsx"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from logic.customer_import import bulk_import_directory

User = get_User_model()


class Command(BaseCommand):
    help = "Import مشتریان از فایل‌های اکسل در دایرکتوری agents"

    def add_arguments(self, parser):
        parser.add_argument(
            "--directory",
            type=str,
            default="agents",
            help="مسیر دایرکتوری حاوی فایل‌های اکسل",
        )
        parser.add_argument(
            "--user",
            type=str,
            default="admin",
            help="نام کاربری برای ثبت لاگ",
        )

    def handle(self, *args, **options):
        directory = options["directory"]
        username = options["user"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR("کاربر مدیر یافت نشد")
                )
                return

        self.stdout.write(
            self.style.SUCCESS(f"شروع import از {directory}...")
        )

        results = bulk_import_directory(directory, user)

        # نمایش نتایج
        total_created = sum(r.get("created", 0) for r in results)
        total_updated = sum(r.get("updated", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        for result in results:
            if "error" in result:
                self.stdout.write(
                    self.style.ERROR(f"❌ {result['file']}: {result['error']}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {result['file']}: {result['created']} جدید، "
                        f"{result['updated']} به‌روز، {result['errors']} خطا"
                    )
                )

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(
            self.style.SUCCESS(
                f"\n📊 جمع کل: {total_created} جدید، {total_updated} به‌روز، {total_errors} خطا"
            )
        )
