# Generated manually for CRM workbook parity with Excel CRM 1405

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0034_dashboard_widgets"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CrmWorkbookRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "sheet",
                    models.CharField(
                        choices=[
                            ("customers", "مشتریان"),
                            ("financial", "مالی"),
                            ("receivables", "وصول مطالبات"),
                            ("suppliers", "تامین کنندگان"),
                            ("saba", "صبا"),
                            ("imobl", "آی مبل"),
                            ("new_production", "تولید جدید"),
                            ("other_orders", "سایر سفارشات"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("invoice_ref", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("data", models.JSONField(blank=True, default=dict)),
                (
                    "source",
                    models.CharField(
                        choices=[("excel", "اکسل"), ("manual", "دستی"), ("sale_sync", "همگام با فروش")],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="crm_workbook_rows",
                        to="backend.sale",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="crm_workbook_edits",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["sheet", "sort_order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="crmworkbookrow",
            index=models.Index(fields=["sheet", "invoice_ref"], name="ix_crm_wb_sheet_inv"),
        ),
        migrations.AddConstraint(
            model_name="crmworkbookrow",
            constraint=models.UniqueConstraint(
                fields=("sheet", "invoice_ref", "sort_order"),
                name="uq_crm_wb_sheet_inv_sort",
            ),
        ),
    ]
