from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0016_seller_staff_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="order_kind",
            field=models.CharField(
                choices=[
                    ("normal", "فروش عادی"),
                    ("pre_invoice", "پیش‌فاکتور"),
                    ("deposit", "بیعانیه"),
                ],
                default="normal",
                max_length=12,
                verbose_name="نوع سفارش",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="order_status",
            field=models.CharField(
                choices=[
                    ("confirmed", "تایید شده"),
                    ("pending", "در انتظار"),
                    ("cancelled", "لغو شده"),
                ],
                default="confirmed",
                max_length=12,
                verbose_name="وضعیت سفارش",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="delivery_date",
            field=models.DateField(blank=True, null=True, verbose_name="تاریخ تحویل"),
        ),
    ]
