"""کیف پول مشتری + تنظیمات پیامک باشگاه."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0009_birthday_sms"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="wallet_balance",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=15,
                verbose_name="موجودی کیف پول",
            ),
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
                    ("order_placed", "ثبت سفارش"),
                    ("discount", "تخفیف ویژه"),
                ],
                default="manual",
                max_length=20,
                verbose_name="نوع پیامک",
            ),
        ),
        migrations.CreateModel(
            name="SmsClubSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shop_name", models.CharField(default="سام اکسون", max_length=100, verbose_name="نام فروشگاه")),
                ("auto_order_placed", models.BooleanField(default=True, verbose_name="پیامک ثبت سفارش")),
                ("auto_welcome", models.BooleanField(default=True, verbose_name="پیامک خوش‌آمدگویی")),
                ("auto_level_up", models.BooleanField(default=True, verbose_name="پیامک ارتقای سطح")),
                (
                    "order_placed_template",
                    models.TextField(
                        default="{name} عزیز، سفارش شما به مبلغ {amount} تومان ثبت شد. {shop_name}",
                        verbose_name="قالب ثبت سفارش",
                    ),
                ),
                (
                    "welcome_template",
                    models.TextField(
                        default="به باشگاه مشتریان {shop_name} خوش آمدید {name}! از همراهی شما سپاسگزاریم.",
                        verbose_name="قالب خوش‌آمدگویی",
                    ),
                ),
                (
                    "level_up_template",
                    models.TextField(
                        default="{name} عزیز، سطح باشگاه شما به «{level}» ارتقا یافت. {shop_name}",
                        verbose_name="قالب ارتقای سطح",
                    ),
                ),
                (
                    "discount_template",
                    models.TextField(
                        default="{name} عزیز! تخفیف ویژه {discount_label} از {shop_name} — منتظر دیدار شما هستیم.",
                        verbose_name="قالب تخفیف ویژه",
                    ),
                ),
                (
                    "default_discount_type",
                    models.CharField(
                        choices=[("amount", "مبلغ ثابت"), ("percent", "درصد")],
                        default="amount",
                        max_length=10,
                        verbose_name="نوع تخفیف پیش‌فرض",
                    ),
                ),
                (
                    "default_discount_value",
                    models.DecimalField(
                        decimal_places=0,
                        default=0,
                        max_digits=15,
                        verbose_name="مقدار تخفیف پیش‌فرض",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")),
            ],
            options={
                "verbose_name": "تنظیمات پیامک باشگاه",
                "verbose_name_plural": "تنظیمات پیامک باشگاه",
            },
        ),
        migrations.CreateModel(
            name="WalletTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=0, max_digits=15, verbose_name="مبلغ (مثبت=واریز)")),
                ("balance_after", models.DecimalField(decimal_places=0, max_digits=15, verbose_name="موجودی پس از تراکنش")),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("deposit", "واریز"),
                            ("withdraw", "برداشت"),
                            ("sale", "پرداخت فروش"),
                            ("refund", "بازگشت"),
                            ("adjustment", "اصلاح"),
                        ],
                        default="adjustment",
                        max_length=12,
                        verbose_name="نوع",
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="شرح")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallet_transactions",
                        to="backend.customer",
                        verbose_name="مشتری",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wallet_transactions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ثبت‌کننده",
                    ),
                ),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wallet_transactions",
                        to="backend.sale",
                        verbose_name="فروش مرتبط",
                    ),
                ),
            ],
            options={
                "verbose_name": "تراکنش کیف پول",
                "verbose_name_plural": "تراکنش‌های کیف پول",
                "ordering": ["-created_at"],
            },
        ),
    ]
