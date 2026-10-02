from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0042_safe_rollout_reconciliation"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="cost_override",
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="profit_mode",
            field=models.CharField(
                choices=[("percent", "درصدی"), ("fixed", "مبلغ ثابت")],
                default="percent",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="target_profit_amount",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(cost_override__isnull=True)
                | models.Q(cost_override__gte=0),
                name="ck_product_cost_override",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(target_profit_amount__gte=0),
                name="ck_product_profit_amount",
            ),
        ),
    ]
