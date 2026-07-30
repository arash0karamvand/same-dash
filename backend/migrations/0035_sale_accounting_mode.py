from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0034_business_amounts_to_rial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="accounting_mode",
            field=models.CharField(
                choices=[("automatic", "حسابداری خودکار"), ("manual", "حسابداری دستی")],
                default="automatic",
                max_length=12,
                verbose_name="نوع ثبت حسابداری",
            ),
        ),
        migrations.AddField(
            model_name="officeorder",
            name="accounting_mode",
            field=models.CharField(
                choices=[("automatic", "حسابداری خودکار"), ("manual", "حسابداری دستی")],
                default="automatic",
                max_length=12,
                verbose_name="نوع ثبت حسابداری",
            ),
        ),
    ]
