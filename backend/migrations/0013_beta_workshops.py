import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0012_frames"),
    ]

    operations = [
        migrations.CreateModel(
            name="BetaCarpentryWorkshop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("name", models.CharField(max_length=150, verbose_name="نام واحد")),
                (
                    "kind",
                    models.CharField(
                        choices=[("internal", "داخل کارخانه"), ("satellite", "کارگاه اقماری")],
                        default="internal",
                        max_length=20,
                        verbose_name="نوع",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "واحد نجاری (بتا)",
                "verbose_name_plural": "واحدهای نجاری (بتا)",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCarpentryOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد دستور")),
                (
                    "kind",
                    models.CharField(
                        choices=[("build", "ساخت کلاف"), ("repair", "تعمیرات")],
                        default="build",
                        max_length=20,
                        verbose_name="نوع",
                    ),
                ),
                ("customer_name", models.CharField(blank=True, default="", max_length=150, verbose_name="مشتری")),
                ("order_ref", models.CharField(blank=True, default="", max_length=80, verbose_name="شماره سفارش")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول / مدل کلاف")),
                ("wood_type", models.CharField(blank=True, default="", max_length=80, verbose_name="جنس چوب")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="تیراژ")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="موعد تحویل")),
                ("freight_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="هزینه باربری")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in_progress", "در حال ساخت / تعمیر"),
                            ("ready", "آماده تحویل"),
                            ("delivered", "تحویل شده به انبار"),
                        ],
                        default="in_progress",
                        max_length=20,
                        verbose_name="وضعیت ساخت",
                    ),
                ),
                ("notes_log", models.JSONField(blank=True, default=list, verbose_name="نظرات و آپدیت‌ها")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_carpentry_orders",
                        to="backend.sale",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "دستور نجاری (بتا)",
                "verbose_name_plural": "دستورهای نجاری (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaPaintOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد سفارش رنگ")),
                ("product_name", models.CharField(max_length=200, verbose_name="نام محصول")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("normal", "تولید عادی"),
                            ("repair", "تعمیرات کارخانه"),
                            ("qc_return", "برگشتی QC"),
                        ],
                        default="normal",
                        max_length=20,
                        verbose_name="نوع سفارش",
                    ),
                ),
                ("color_name", models.CharField(blank=True, default="", max_length=80, verbose_name="فام رنگ")),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("raw", "ورود کلاف خام"),
                            ("sanding", "سنباده و زیرسازی"),
                            ("putty", "بتونه و آستر اول"),
                            ("sealer", "سیلر و پوستاب"),
                            ("topcoat", "رنگ رویه اصلی"),
                            ("patina", "پتینه و هایلایت"),
                            ("pu_final", "پلی‌اورتان نهایی"),
                            ("qc", "کنترل کیفیت و تحویل"),
                        ],
                        default="raw",
                        max_length=20,
                        verbose_name="مرحله خط",
                    ),
                ),
                ("progress", models.PositiveIntegerField(default=0, verbose_name="پیشرفت")),
                ("qc_issue", models.TextField(blank=True, default="", verbose_name="ایراد QC")),
                ("notes_log", models.JSONField(blank=True, default=list, verbose_name="لاگ و یادداشت‌ها")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_paint_orders",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "سفارش رنگ (بتا)",
                "verbose_name_plural": "سفارش‌های رنگ (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaUpholsteryJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="شناسه کار")),
                ("order_ref", models.CharField(blank=True, default="", max_length=80, verbose_name="شماره سفارش")),
                ("product_name", models.CharField(max_length=200, verbose_name="مدل مبلمان")),
                ("foam_material", models.CharField(blank=True, default="", max_length=200, verbose_name="متریال فوم و نشیمن")),
                ("craftsman", models.CharField(blank=True, default="", max_length=120, verbose_name="استادکار رویه‌کوب")),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("webbing", "تسمه‌کشی و فنربندی"),
                            ("foam", "نصب فوم سرد و اسفنج"),
                            ("fabric", "کشیدن پارچه و لمسه‌دوزی"),
                            ("finishing", "میخ‌کاری، سرمه‌دوزی و اتوکشی"),
                            ("qc", "تکمیل و ارسال به کنترل کیفیت (QC)"),
                        ],
                        default="webbing",
                        max_length=20,
                        verbose_name="مرحله فنی",
                    ),
                ),
                ("progress", models.PositiveIntegerField(default=0, verbose_name="پیشرفت")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="موعد تحویل")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_upholstery_jobs",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "کار رویه‌کوبی (بتا)",
                "verbose_name_plural": "کارهای رویه‌کوبی (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaFabricRoll",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد پارچه")),
                ("color_name", models.CharField(blank=True, default="", max_length=80, verbose_name="رنگ")),
                ("company", models.CharField(blank=True, default="", max_length=120, verbose_name="شرکت / برند")),
                ("fabric_type", models.CharField(blank=True, default="", max_length=80, verbose_name="جنس پارچه")),
                ("country", models.CharField(blank=True, default="", max_length=80, verbose_name="کشور سازنده")),
                ("unit_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="بهای خرید هر متر")),
                ("meters", models.DecimalField(decimal_places=3, default=0, max_digits=18, verbose_name="متراژ")),
                ("image_url", models.URLField(blank=True, default="", verbose_name="تصویر")),
                ("min_meters", models.DecimalField(decimal_places=3, default=0, max_digits=18, verbose_name="حداقل موجودی")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "طاقه پارچه (بتا)",
                "verbose_name_plural": "طاقه‌های پارچه (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaFabricDispatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="شماره حواله")),
                ("destination", models.CharField(max_length=150, verbose_name="کارگاه مقصد")),
                ("meters", models.DecimalField(decimal_places=3, max_digits=18, verbose_name="متراژ ارسالی")),
                ("sent_date", models.DateField(verbose_name="تاریخ ارسال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "roll",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dispatches",
                        to="backend.betafabricroll",
                    ),
                ),
            ],
            options={
                "verbose_name": "حواله خروج پارچه (بتا)",
                "verbose_name_plural": "حواله‌های خروج پارچه (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaQcInspection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد بازرسی")),
                ("order_ref", models.CharField(blank=True, default="", max_length=80, verbose_name="شماره سفارش")),
                ("buyer_name", models.CharField(blank=True, default="", max_length=150, verbose_name="خریدار")),
                ("invoice_ref", models.CharField(blank=True, default="", max_length=80, verbose_name="فاکتور")),
                ("origin", models.CharField(blank=True, default="", max_length=150, verbose_name="مبدا ساخت")),
                ("product_name", models.CharField(max_length=200, verbose_name="محصول")),
                ("requirements", models.TextField(blank=True, default="", verbose_name="الزامات")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="تیراژ")),
                ("wood_color", models.CharField(blank=True, default="", max_length=80, verbose_name="رنگ چوب")),
                ("fabric_color", models.CharField(blank=True, default="", max_length=80, verbose_name="پارچه")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "در انتظار بازرسی"),
                            ("rework", "نیازمند بازکاری"),
                            ("approved", "تایید شده"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="وضعیت بررسی",
                    ),
                ),
                (
                    "grade",
                    models.CharField(
                        blank=True,
                        choices=[("A", "Grade A"), ("B", "Grade B"), ("C", "Grade C")],
                        default="",
                        max_length=4,
                        verbose_name="گرید",
                    ),
                ),
                ("scan_url", models.URLField(blank=True, default="", verbose_name="برگه اسکن")),
                ("entered_at", models.DateField(blank=True, null=True, verbose_name="تاریخ ورود به QC")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beta_qc_inspections",
                        to="backend.sale",
                    ),
                ),
            ],
            options={
                "verbose_name": "بازرسی کنترل کیفیت (بتا)",
                "verbose_name_plural": "بازرسی‌های کنترل کیفیت (بتا)",
                "ordering": ["-id"],
            },
        ),
    ]
