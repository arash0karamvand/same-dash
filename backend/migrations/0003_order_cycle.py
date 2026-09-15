"""Configurable sale cycle, warehouses, and fulfillment routing."""

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


NEW_STAGES = [
    ("in_warehouse", "در انبار", 7, False),
    ("ready_for_pickup", "آماده تحویل حضوری", 8, False),
    ("merchant_assigned", "بازرگان — صف کارخانه", 9, False),
]

SLOT_SPECS = [
    ("branch_supervisor", "سرپرست شعبه", "fixed", True, 1),
    ("shop_crm_monitor", "ناظر فروشگاه و CRM", "monitor", True, 2),
    ("crm", "اداری CRM", "fixed", True, 3),
    ("factory", "کارخانه", "route", True, 10),
    ("warehouse", "انبار", "route", True, 11),
    ("customer_pickup", "تحویل به مشتری", "route", True, 12),
    ("merchant", "بازرگان", "route", True, 13),
    ("fulfillment_supervisor", "ناظر همه مسیرها", "monitor", True, 20),
]


def seed_cycle_and_stages(apps, schema_editor):
    WorkflowStage = apps.get_model("backend", "WorkflowStage")
    for code, label, sort_order, is_terminal in NEW_STAGES:
        WorkflowStage.objects.update_or_create(
            code=code,
            defaults={"label": label, "sort_order": sort_order, "is_terminal": is_terminal, "is_active": True},
        )
    WorkflowStage.objects.filter(code="completed").update(sort_order=10)

    OrderCycle = apps.get_model("backend", "OrderCycle")
    CycleSlot = apps.get_model("backend", "CycleSlot")
    cycle = OrderCycle.objects.filter(is_active=True).first()
    if cycle is None:
        cycle = OrderCycle.objects.create(name="چرخه فروش", is_active=True)
    for step_key, label, kind, is_enabled, sort_order in SLOT_SPECS:
        CycleSlot.objects.update_or_create(
            cycle=cycle,
            step_key=step_key,
            defaults={
                "label": label,
                "kind": kind,
                "is_enabled": is_enabled,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("backend", "0002_seed_chart_of_accounts"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=40, unique=True, verbose_name="کد انبار")),
                ("label", models.CharField(max_length=80, verbose_name="نام انبار")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        db_column="branch",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="warehouses",
                        to="backend.branch",
                        to_field="code",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "label"]},
        ),
        migrations.CreateModel(
            name="OrderCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="چرخه فروش", max_length=80)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-is_active", "id"]},
        ),
        migrations.CreateModel(
            name="CycleSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_key", models.SlugField(max_length=40)),
                ("label", models.CharField(max_length=100)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("fixed", "مرحله ثابت"),
                            ("monitor", "نظارت"),
                            ("route", "مسیر ارسال"),
                        ],
                        default="fixed",
                        max_length=20,
                    ),
                ),
                (
                    "assignee_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "تعیین‌نشده"),
                            ("user", "کاربر"),
                            ("rank", "مقام"),
                        ],
                        default="",
                        max_length=10,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "cycle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="backend.ordercycle",
                    ),
                ),
                (
                    "org_rank",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cycle_slots",
                        to="backend.orgrank",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cycle_slots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "step_key"]},
        ),
        migrations.AddConstraint(
            model_name="cycleslot",
            constraint=models.UniqueConstraint(fields=("cycle", "step_key"), name="uq_cycle_step_key"),
        ),
        migrations.AddField(
            model_name="sale",
            name="fulfillment_route",
            field=models.CharField(
                blank=True,
                choices=[
                    ("factory", "کارخانه"),
                    ("warehouse", "انبار"),
                    ("customer_pickup", "تحویل به مشتری"),
                    ("merchant", "بازرگان"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="fulfillment_warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fulfillment_orders",
                to="backend.warehouse",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="fulfillment_source_branch",
            field=models.ForeignKey(
                blank=True,
                db_column="fulfillment_source_branch",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fulfillment_source_orders",
                to="backend.branch",
                to_field="code",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="merchant_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="merchant_sales",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="warehouse_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="pickup_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(seed_cycle_and_stages, migrations.RunPython.noop),
    ]
