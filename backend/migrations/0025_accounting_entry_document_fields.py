# Generated manually — فیلدهای کد سند، افتتاحیه و مانده

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0024_accounting_chart"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountingentry",
            name="document_code",
            field=models.CharField(blank=True, db_index=True, max_length=30, verbose_name="کد سند"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="opening_debit",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="افتتاحیه بدهکار"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="opening_credit",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="افتتاحیه بستانکار"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="balance_debit",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="مانده بدهکار"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="balance_credit",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="مانده بستانکار"),
        ),
    ]
