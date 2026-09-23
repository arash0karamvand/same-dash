from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0025_assistancerequest_attendanceconfirmation_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TradeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[
                    ("purchase", "خرید"),
                    ("purchase_return", "برگشت از خرید"),
                    ("sale", "فروش"),
                    ("sale_return", "برگشت از فروش"),
                    ("purchase_discount", "تخفیف نقدی خرید"),
                    ("sale_discount", "تخفیف نقدی فروش"),
                ], max_length=24)),
                ("settlement", models.CharField(choices=[("cash", "نقد"), ("credit", "نسیه")], default="credit", max_length=10)),
                ("quantity", models.DecimalField(decimal_places=3, default=0, max_digits=18)),
                ("remaining_qty", models.DecimalField(decimal_places=3, default=0, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("trade_discount", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("freight", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("insurance", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("other_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("goods_net", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("charges", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("inventory_amount", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("vat_rate", models.DecimalField(decimal_places=2, default=10, max_digits=5)),
                ("vat_amount", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("cogs_amount", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("cash_discount", models.DecimalField(decimal_places=0, default=0, max_digits=18)),
                ("invoice_number", models.CharField(blank=True, max_length=60)),
                ("warehouse_receipt", models.CharField(blank=True, max_length=60)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("inventory_move", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trade_documents", to="backend.inventorytransaction")),
                ("journal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trade_documents", to="backend.journalentry")),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trade_documents", to="backend.material")),
                ("source", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="adjustments", to="backend.tradedocument")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="tradedocument",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_trade_qty"),
        ),
        migrations.AddConstraint(
            model_name="tradedocument",
            constraint=models.CheckConstraint(condition=models.Q(remaining_qty__gte=0), name="ck_trade_remaining"),
        ),
        migrations.AddConstraint(
            model_name="tradedocument",
            constraint=models.CheckConstraint(condition=models.Q(vat_rate__gte=0), name="ck_trade_vat_rate"),
        ),
    ]
