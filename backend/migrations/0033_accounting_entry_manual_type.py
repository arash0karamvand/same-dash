# Generated manually — نوع سند «دستی»

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0032_account_hierarchy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountingentry",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("manual", "دستی"),
                    ("sale", "فروش"),
                    ("receivable", "مطالبات (بدهکار مشتری)"),
                    ("payment", "دریافت / پرداخت"),
                    ("refund", "مرجوعی"),
                    ("adjustment", "تعدیل"),
                    ("other", "سایر"),
                ],
                default="sale",
                max_length=20,
                verbose_name="نوع سند",
            ),
        ),
    ]
