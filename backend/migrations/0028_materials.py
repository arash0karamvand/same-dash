"""متریال و ارتباط محصول–متریال."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0027_accounting_entry_account_hierarchy"),
    ]

    operations = [
        migrations.CreateModel(
            name="Material",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=150, verbose_name="نام متریال")),
                ("color_name", models.CharField(blank=True, max_length=50, verbose_name="نام رنگ")),
                ("color_hex", models.CharField(default="#cccccc", max_length=7, verbose_name="کد رنگ")),
                ("sku", models.CharField(blank=True, db_index=True, max_length=50, verbose_name="کد")),
                ("unit", models.CharField(default="متر", max_length=20, verbose_name="واحد")),
                ("unit_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="قیمت واحد (تمام‌شده)")),
                ("stock", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="موجودی")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")),
            ],
            options={
                "verbose_name": "متریال",
                "verbose_name_plural": "متریال‌ها",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ProductMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12, verbose_name="مقدار مصرف")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_links",
                        to="backend.material",
                        verbose_name="متریال",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_materials",
                        to="backend.product",
                        verbose_name="محصول",
                    ),
                ),
            ],
            options={
                "verbose_name": "متریال محصول",
                "verbose_name_plural": "متریال‌های محصول",
                "ordering": ["sort_order", "id"],
                "unique_together": {("product", "material")},
            },
        ),
    ]
