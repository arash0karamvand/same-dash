import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0012_sale_discount_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="نام دسته")),
                ("description", models.TextField(blank=True, verbose_name="توضیحات")),
                ("color", models.CharField(default="#6366f1", max_length=7, verbose_name="رنگ نمایش")),
                ("icon", models.CharField(blank=True, default="📦", max_length=8, verbose_name="آیکون")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")),
            ],
            options={
                "verbose_name": "دسته محصول",
                "verbose_name_plural": "دسته‌های محصول",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="brand",
            field=models.CharField(blank=True, max_length=100, verbose_name="برند"),
        ),
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, verbose_name="توضیحات"),
        ),
        migrations.AddField(
            model_name="product",
            name="sku",
            field=models.CharField(blank=True, db_index=True, max_length=50, verbose_name="کد محصول"),
        ),
        migrations.AddField(
            model_name="product",
            name="unit",
            field=models.CharField(default="عدد", max_length=20, verbose_name="واحد"),
        ),
        migrations.AddField(
            model_name="product",
            name="attributes",
            field=models.JSONField(blank=True, default=dict, verbose_name="ویژگی‌های سفارشی"),
        ),
        migrations.AddField(
            model_name="product",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی"),
        ),
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="backend.productcategory",
                verbose_name="دسته",
            ),
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("color_name", models.CharField(max_length=50, verbose_name="نام رنگ")),
                ("color_hex", models.CharField(default="#cccccc", max_length=7, verbose_name="کد رنگ")),
                ("sku", models.CharField(blank=True, max_length=60, verbose_name="کد تنوع")),
                ("price", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="قیمت")),
                ("stock", models.PositiveIntegerField(blank=True, null=True, verbose_name="موجودی")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="backend.product",
                        verbose_name="محصول",
                    ),
                ),
            ],
            options={
                "verbose_name": "تنوع محصول",
                "verbose_name_plural": "تنوع‌های محصول",
                "ordering": ["sort_order", "id"],
                "unique_together": {("product", "color_name")},
            },
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_lines",
                to="backend.productvariant",
                verbose_name="تنوع",
            ),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="color_name",
            field=models.CharField(blank=True, max_length=50, verbose_name="رنگ"),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="color_hex",
            field=models.CharField(blank=True, max_length=7, verbose_name="کد رنگ"),
        ),
    ]
