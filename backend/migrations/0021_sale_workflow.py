"""گردش کار سفارش — فیلدهای مرحله و تایید."""

from django.conf import settings
from django.db import migrations, models


def migrate_workflow_stages(apps, schema_editor):
    Sale = apps.get_model("backend", "Sale")
    Sale.objects.filter(order_status="pending").update(workflow_stage="pending_branch")


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0020_dynamic_config"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="workflow_stage",
            field=models.CharField(
                choices=[
                    ("pending_branch", "منتظر سرپرست شعبه"),
                    ("branch_approved", "منتظر حسابداری"),
                    ("accounting_approved", "ارسال به کارخانه"),
                    ("in_production", "در حال ساخت"),
                    ("production_done", "آماده باربری"),
                    ("in_freight", "در باربری"),
                    ("completed", "تکمیل شده"),
                ],
                db_index=True,
                default="completed",
                max_length=24,
                verbose_name="مرحله گردش کار",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="branch_approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاریخ تایید سرپرست"),
        ),
        migrations.AddField(
            model_name="sale",
            name="branch_approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="branch_approved_sales",
                to=settings.AUTH_USER_MODEL,
                verbose_name="تاییدکننده سرپرست",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="accounting_approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاریخ تایید حسابداری"),
        ),
        migrations.AddField(
            model_name="sale",
            name="accounting_approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="accounting_approved_sales",
                to=settings.AUTH_USER_MODEL,
                verbose_name="تاییدکننده حسابداری",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="factory_received_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="دریافت کارخانه"),
        ),
        migrations.AddField(
            model_name="sale",
            name="factory_received_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="factory_received_sales",
                to=settings.AUTH_USER_MODEL,
                verbose_name="دریافت‌کننده کارخانه",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="production_done_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="پایان ساخت"),
        ),
        migrations.AddField(
            model_name="sale",
            name="freight_received_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="دریافت باربری"),
        ),
        migrations.AddField(
            model_name="sale",
            name="freight_received_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="freight_received_sales",
                to=settings.AUTH_USER_MODEL,
                verbose_name="دریافت‌کننده باربری",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="freight_completed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تکمیل باربری"),
        ),
        migrations.RunPython(migrate_workflow_stages, migrations.RunPython.noop),
    ]
