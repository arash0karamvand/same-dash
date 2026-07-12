"""فیلدهای انتشار — سفارش فقط پس از تایید در صف بعدی قابل مشاهده است."""

from django.db import migrations, models
from django.db.models import F


def backfill_release_timestamps(apps, schema_editor):
    Sale = apps.get_model("backend", "Sale")
    Sale.objects.filter(
        workflow_stage__in=[
            "branch_approved",
            "accounting_approved",
            "in_production",
            "production_done",
            "in_freight",
            "completed",
        ],
        office_released_at__isnull=True,
    ).update(office_released_at=F("branch_approved_at"))
    Sale.objects.filter(
        workflow_stage__in=[
            "accounting_approved",
            "in_production",
            "production_done",
            "in_freight",
            "completed",
        ],
        factory_released_at__isnull=True,
    ).update(factory_released_at=F("accounting_approved_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0021_sale_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="office_released_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="زمان انتشار برای اداری",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="factory_released_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="زمان انتشار برای کارخانه",
            ),
        ),
        migrations.RunPython(backfill_release_timestamps, migrations.RunPython.noop),
    ]
