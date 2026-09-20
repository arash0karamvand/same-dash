from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0016_workshop_recipes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sale",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sales",
                to="backend.customer",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="receive_kind",
            field=models.CharField(
                choices=[
                    ("customer", "مشتری"),
                    ("branch_floor", "کف شعبه"),
                    ("warehouse", "انبار"),
                    ("merchant", "بازرگان"),
                    ("repair", "تعمیر"),
                ],
                db_index=True,
                default="customer",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="contract_party",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="sale",
            name="source_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="derived_factory_jobs",
                to="backend.sale",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="webbing_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products_webbing",
                to="backend.workshoprecipe",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="build_model",
            field=models.CharField(
                choices=[("frame_line", "خط کلاف")],
                db_index=True,
                default="frame_line",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="needs_paint",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="product",
            name="pipeline_end",
            field=models.CharField(
                choices=[("upholstery", "رویه‌کوبی"), ("assembly", "مونتاژ")],
                default="upholstery",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="material",
            name="usage_kind",
            field=models.CharField(
                choices=[
                    ("wood", "چوب"),
                    ("paint", "رنگ"),
                    ("fabric", "پارچه"),
                    ("foam", "اسفنج"),
                    ("cushion", "کوسن"),
                    ("webbing", "تسمه"),
                    ("other", "سایر"),
                ],
                db_index=True,
                default="other",
                max_length=20,
                verbose_name="نوع مصرف کارخانه",
            ),
        ),
        migrations.AlterField(
            model_name="workshoprecipe",
            name="kind",
            field=models.CharField(
                choices=[
                    ("paint", "رنگ"),
                    ("fabric", "پارچه"),
                    ("foam", "اسفنج"),
                    ("cushion", "کوسن"),
                    ("webbing", "تسمه"),
                ],
                db_index=True,
                max_length=20,
                verbose_name="نوع دستور",
            ),
        ),
        migrations.CreateModel(
            name="BetaAssemblyJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد کار مونتاژ")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                (
                    "assembly_name",
                    models.CharField(blank=True, default="", max_length=150, verbose_name="شرح مونتاژ"),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("queue", "صف مونتاژ"),
                            ("assemble", "در حال مونتاژ"),
                            ("done", "آماده QC"),
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
                        related_name="beta_assembly_jobs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "کار مونتاژ",
                "verbose_name_plural": "کارهای مونتاژ",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaClearanceJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد ترخیص")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                (
                    "destination",
                    models.CharField(blank=True, default="", max_length=40, verbose_name="مقصد"),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("queue", "صف ترخیص"),
                            ("check", "بررسی خروج"),
                            ("released", "ترخیص‌شده"),
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
                        related_name="beta_clearance_jobs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "کار ترخیص",
                "verbose_name_plural": "کارهای ترخیص",
                "ordering": ["-id"],
            },
        ),
    ]
