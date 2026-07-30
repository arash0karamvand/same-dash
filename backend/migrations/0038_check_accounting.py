# Generated manually for check accounting fields

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0037_factory_accounting"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="saleinstallment",
            name="received_at",
            field=models.DateField(blank=True, null=True, verbose_name="تاریخ تحویل چک به شعبه"),
        ),
        migrations.AddField(
            model_name="saleinstallment",
            name="receiver_name",
            field=models.CharField(blank=True, max_length=120, verbose_name="تحویل‌گیرنده"),
        ),
        migrations.AddField(
            model_name="saleinstallment",
            name="registration_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="check_registrations",
                to="backend.account",
                verbose_name="حساب ثبت چک",
            ),
        ),
        migrations.AddField(
            model_name="saleinstallment",
            name="deposit_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="check_deposits",
                to="backend.account",
                verbose_name="حساب واریز چک",
            ),
        ),
        migrations.AddField(
            model_name="saleinstallment",
            name="accounting_registered_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاریخ ثبت حسابداری چک"),
        ),
        migrations.AddField(
            model_name="saleinstallment",
            name="accounting_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="installment_checks",
                to="backend.accountingentry",
                verbose_name="سند ثبت چک",
            ),
        ),
        migrations.CreateModel(
            name="UserAccountingPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="به‌روزرسانی")),
                (
                    "default_check_deposit_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preferred_for_check_deposit",
                        to="backend.account",
                        verbose_name="حساب پیش‌فرض واریز چک",
                    ),
                ),
                (
                    "default_check_registration_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preferred_for_check_registration",
                        to="backend.account",
                        verbose_name="حساب پیش‌فرض ثبت چک",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounting_preference",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "ترجیح حسابداری کاربر",
                "verbose_name_plural": "ترجیحات حسابداری کاربران",
            },
        ),
    ]
