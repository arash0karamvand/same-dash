# Generated manually — paid_amount on Sale + receivable/payment entry types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0003_smslog_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="paid_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="برای پرداخت بخشی یا تسویه اقساط.",
                max_digits=18,
                verbose_name="مبلغ پرداخت‌شده",
            ),
        ),
        migrations.AlterField(
            model_name="accountingentry",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("sale", "فروش"),
                    ("receivable", "مطالبات (بدهکار مشتری)"),
                    ("payment", "دریافت قسط/پرداخت"),
                    ("refund", "مرجوعی"),
                    ("adjustment", "اصلاح"),
                    ("other", "سایر"),
                ],
                default="sale",
                max_length=20,
                verbose_name="نوع سند",
            ),
        ),
    ]
