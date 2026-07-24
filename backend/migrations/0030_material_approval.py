"""تایید متریال — گردش کارخانه → اداری."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def approve_existing_materials(apps, schema_editor):
    Material = apps.get_model("backend", "Material")
    Material.objects.filter(is_deleted=False).update(approval_status="approved", is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0029_factory_order_materials_deducted"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("pending", "در انتظار تایید اداری"),
                    ("approved", "تایید شده"),
                    ("rejected", "رد شده"),
                ],
                db_index=True,
                default="approved",
                max_length=16,
                verbose_name="وضعیت تایید",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاریخ تایید"),
        ),
        migrations.AddField(
            model_name="material",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_materials",
                to=settings.AUTH_USER_MODEL,
                verbose_name="تاییدکننده",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="rejection_reason",
            field=models.TextField(blank=True, verbose_name="دلیل رد"),
        ),
        migrations.AddField(
            model_name="material",
            name="submitted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submitted_materials",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ثبت‌کننده",
            ),
        ),
        migrations.RunPython(approve_existing_materials, migrations.RunPython.noop),
    ]
