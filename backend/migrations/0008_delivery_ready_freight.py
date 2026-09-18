from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0007_ticket_messages"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="delivery_ready_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="delivery_ready_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="delivery_ready_sales",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="early_disposition_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sale",
            name="early_ship_allowed_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="early_disposition_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="early_disposition_sales",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="shipped_early",
            field=models.BooleanField(default=False),
        ),
    ]
