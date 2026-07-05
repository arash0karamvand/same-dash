from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0011_club_roles_reminders"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="discount_type",
            field=models.CharField(
                choices=[
                    ("percent", "درصدی"),
                    ("amount", "مبلغ ثابت"),
                    ("wallet", "موجودی حساب"),
                ],
                default="amount",
                max_length=10,
                verbose_name="نوع تخفیف",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="discount_value",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=14,
                verbose_name="مقدار تخفیف (ورودی)",
            ),
        ),
    ]
