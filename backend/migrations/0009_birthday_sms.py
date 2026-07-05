"""تولد مشتری + پیامک خودکار تبریک تولد."""

from datetime import time

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0008_attendance_check_times"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="birthday",
            field=models.DateField(blank=True, null=True, verbose_name="تاریخ تولد"),
        ),
        migrations.AlterField(
            model_name="smslog",
            name="sms_type",
            field=models.CharField(
                choices=[
                    ("manual", "دستی"),
                    ("welcome", "خوش‌آمدگویی"),
                    ("level_up", "ارتقای سطح"),
                    ("promotion", "تبلیغاتی"),
                    ("birthday", "تبریک تولد"),
                ],
                default="manual",
                max_length=20,
                verbose_name="نوع پیامک",
            ),
        ),
        migrations.CreateModel(
            name="BirthdaySmsSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=False, verbose_name="فعال")),
                (
                    "message_template",
                    models.TextField(
                        default="تولدت مبارک {name}! از طرف {shop_name} بهترین‌ها را برایت آرزومندیم.",
                        verbose_name="قالب پیام",
                    ),
                ),
                ("shop_name", models.CharField(default="سام اکسون", max_length=100, verbose_name="نام فروشگاه")),
                ("send_time", models.TimeField(default=time(10, 0), verbose_name="ساعت ارسال")),
                ("last_run_date", models.DateField(blank=True, null=True, verbose_name="آخرین ارسال خودکار")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")),
            ],
            options={
                "verbose_name": "تنظیمات پیامک تولد",
                "verbose_name_plural": "تنظیمات پیامک تولد",
            },
        ),
        migrations.CreateModel(
            name="BirthdaySmsExclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exclude_date", models.DateField(verbose_name="تاریخ ارسال (روز جاری)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="birthday_sms_exclusions",
                        to="backend.customer",
                        verbose_name="مشتری",
                    ),
                ),
            ],
            options={
                "verbose_name": "استثناء پیامک تولد",
                "verbose_name_plural": "استثناءهای پیامک تولد",
                "unique_together": {("customer", "exclude_date")},
            },
        ),
    ]
