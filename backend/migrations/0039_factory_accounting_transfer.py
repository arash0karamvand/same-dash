from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0038_check_accounting"),
    ]

    operations = [
        migrations.AddField(
            model_name="factoryaccountingentry",
            name="office_document_code",
            field=models.CharField(blank=True, max_length=40, verbose_name="کد سند اداری"),
        ),
        migrations.AddField(
            model_name="factoryaccountingentry",
            name="transferred_to_office_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="انتقال به اداری",
            ),
        ),
        migrations.AlterField(
            model_name="accountingentry",
            name="attach_code",
            field=models.CharField(blank=True, max_length=40, verbose_name="ع"),
        ),
        migrations.AlterField(
            model_name="factoryaccountingentry",
            name="attach_code",
            field=models.CharField(blank=True, max_length=40, verbose_name="ع"),
        ),
    ]
