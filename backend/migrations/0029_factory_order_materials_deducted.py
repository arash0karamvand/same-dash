"""کسر متریال سفارش کارخانه."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0028_materials"),
    ]

    operations = [
        migrations.AddField(
            model_name="factoryorder",
            name="materials_deducted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="کسر متریال"),
        ),
    ]
