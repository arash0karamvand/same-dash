from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("backend", "0022_fabric_catalog_tree"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaterialStocktake",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("count_type", models.CharField(choices=[("cycle", "دوره‌ای"), ("annual", "پایان سال"), ("spot", "موردی")], default="cycle", max_length=20, verbose_name="نوع شمارش")),
                ("status", models.CharField(choices=[("draft", "پیش‌نویس"), ("closed", "بسته شده")], db_index=True, default="draft", max_length=20, verbose_name="وضعیت")),
                ("scope_note", models.CharField(blank=True, default="", max_length=200, verbose_name="محدوده")),
                ("supervisor_name", models.CharField(blank=True, default="", max_length=120, verbose_name="سرپرست")),
                ("counter_names", models.CharField(blank=True, default="", max_length=240, verbose_name="شمارش‌گرها")),
                ("observer_name", models.CharField(blank=True, default="", max_length=120, verbose_name="ناظر")),
                ("started_at", models.DateTimeField(verbose_name="شروع")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="پایان")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="material_stocktakes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "برگه انبارگردانی",
                "verbose_name_plural": "برگه‌های انبارگردانی",
                "ordering": ["-started_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="MaterialStocktakeLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("system_qty", models.DecimalField(decimal_places=3, max_digits=18, verbose_name="موجودی سیستمی")),
                ("physical_qty", models.DecimalField(decimal_places=3, max_digits=18, verbose_name="موجودی فیزیکی")),
                ("unit_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="قیمت واحد")),
                ("condition", models.CharField(choices=[("sound", "سالم"), ("damaged", "آسیب‌دیده"), ("expired", "تاریخ‌گذشته"), ("consignment", "امانی")], default="sound", max_length=20, verbose_name="وضعیت کیفی")),
                ("root_cause", models.CharField(blank=True, default="", max_length=32, verbose_name="علت مغایرت")),
                ("material", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="stocktake_lines", to="backend.material")),
                ("stocktake", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="lines", to="backend.materialstocktake")),
            ],
            options={
                "verbose_name": "ردیف انبارگردانی",
                "verbose_name_plural": "ردیف‌های انبارگردانی",
                "ordering": ["material_id"],
                "constraints": [
                    models.UniqueConstraint(fields=("stocktake", "material"), name="uq_stocktake_material"),
                    models.CheckConstraint(condition=models.Q(physical_qty__gte=0), name="ck_stocktake_physical"),
                    models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_stocktake_line_cost"),
                ],
            },
        ),
    ]
