from django.db import migrations, models


def migrate_legacy_payment_methods(apps, schema_editor):
    Sale = apps.get_model("backend", "Sale")
    SaleInstallment = apps.get_model("backend", "SaleInstallment")
    Sale.objects.filter(payment_method__in=("online", "credit")).update(payment_method="cash")
    SaleInstallment.objects.filter(payment_method__in=("online", "credit")).update(payment_method="cash")


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0017_sale_order_kind_deposit"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_payment_methods, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sale",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("cash", "نقدی"),
                    ("card", "کارت‌خوان"),
                    ("check", "چک"),
                ],
                default="cash",
                max_length=10,
                verbose_name="روش پرداخت",
            ),
        ),
        migrations.AlterField(
            model_name="saleinstallment",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("cash", "نقدی"),
                    ("card", "کارت‌خوان"),
                    ("check", "چک"),
                ],
                default="cash",
                max_length=10,
                verbose_name="روش پرداخت",
            ),
        ),
    ]
