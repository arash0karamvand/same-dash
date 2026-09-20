import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0015_beta_carpentry_modules"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="usage_kind",
            field=models.CharField(
                choices=[
                    ("wood", "چوب"),
                    ("paint", "رنگ"),
                    ("fabric", "پارچه"),
                    ("foam", "فوم"),
                    ("cushion", "کوسن"),
                    ("other", "سایر"),
                ],
                db_index=True,
                default="other",
                max_length=20,
                verbose_name="نوع مصرف کارخانه",
            ),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="workset_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="WorkshopRecipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("paint", "رنگ"),
                            ("fabric", "پارچه"),
                            ("foam", "فوم"),
                            ("cushion", "کوسن"),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name="نوع دستور",
                    ),
                ),
                ("name", models.CharField(max_length=150, verbose_name="نام")),
                ("color_name", models.CharField(blank=True, default="", max_length=80, verbose_name="رنگ / فام")),
                ("note", models.TextField(blank=True, default="", verbose_name="توضیحات")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "دستور دست‌کار",
                "verbose_name_plural": "دستورهای دست‌کار",
                "ordering": ["kind", "name"],
            },
        ),
        migrations.CreateModel(
            name="WorkshopRecipeMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=18, verbose_name="مقدار")),
                ("unit", models.CharField(blank=True, default="", max_length=20, verbose_name="واحد")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="workshop_recipe_links",
                        to="backend.material",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="materials",
                        to="backend.workshoprecipe",
                    ),
                ),
            ],
            options={
                "verbose_name": "متریال دستور دست‌کار",
                "verbose_name_plural": "متریال‌های دستور دست‌کار",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="workshoprecipematerial",
            constraint=models.UniqueConstraint(fields=("recipe", "material"), name="uq_workshop_recipe_material"),
        ),
        migrations.AddConstraint(
            model_name="workshoprecipematerial",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_workshop_recipe_qty"),
        ),
        migrations.AddField(
            model_name="product",
            name="paint_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products_paint",
                to="backend.workshoprecipe",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="fabric_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products_fabric",
                to="backend.workshoprecipe",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="foam_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products_foam",
                to="backend.workshoprecipe",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="cushion_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products_cushion",
                to="backend.workshoprecipe",
            ),
        ),
        migrations.CreateModel(
            name="BetaFoamJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد کار فوم")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                ("foam_name", models.CharField(blank=True, default="", max_length=150, verbose_name="دستور فوم")),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("queue", "صف برش"),
                            ("cut", "برش فوم"),
                            ("install", "نصب روی کلاف"),
                            ("done", "آماده رویه‌کوبی"),
                        ],
                        default="queue",
                        max_length=20,
                        verbose_name="مرحله",
                    ),
                ),
                ("progress", models.PositiveIntegerField(default=0, verbose_name="پیشرفت")),
                ("notes_log", models.JSONField(blank=True, default=list, verbose_name="لاگ")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_foam_jobs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "کار فوم",
                "verbose_name_plural": "کارهای فوم",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCushionJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد کار کوسن")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                ("cushion_name", models.CharField(blank=True, default="", max_length=150, verbose_name="دستور کوسن")),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("queue", "صف دوخت"),
                            ("cut", "برش پارچه کوسن"),
                            ("sew", "دوخت و پر کردن"),
                            ("done", "آماده مونتاژ"),
                        ],
                        default="queue",
                        max_length=20,
                        verbose_name="مرحله",
                    ),
                ),
                ("progress", models.PositiveIntegerField(default=0, verbose_name="پیشرفت")),
                ("notes_log", models.JSONField(blank=True, default=list, verbose_name="لاگ")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_cushion_jobs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "کار کوسن",
                "verbose_name_plural": "کارهای کوسن",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaFabricNeed",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد نیاز پارچه")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                ("color_name", models.CharField(blank=True, default="", max_length=80, verbose_name="رنگ پارچه")),
                ("recipe_name", models.CharField(blank=True, default="", max_length=150, verbose_name="دستور پارچه")),
                ("meters", models.DecimalField(decimal_places=3, default=0, max_digits=18, verbose_name="متراژ مورد نیاز")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "نیاز ثبت‌شده"),
                            ("reserved", "رزرو شده"),
                            ("issued", "حواله شده"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="وضعیت",
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
                        related_name="beta_fabric_needs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "نیاز پارچه خط تولید",
                "verbose_name_plural": "نیازهای پارچه خط تولید",
                "ordering": ["-id"],
            },
        ),
    ]
