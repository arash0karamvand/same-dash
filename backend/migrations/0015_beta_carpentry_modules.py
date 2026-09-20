import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0014_beta_carpentry_frame"),
    ]

    operations = [
        migrations.CreateModel(
            name="BetaCarpentryTool",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد")),
                ("name", models.CharField(max_length=150, verbose_name="نام ابزار / دستگاه")),
                ("category", models.CharField(blank=True, default="", max_length=80, verbose_name="دسته")),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "فعال"), ("maintenance", "در تعمیر"), ("retired", "اسقاط")],
                        default="active",
                        max_length=20,
                        verbose_name="وضعیت",
                    ),
                ),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="تعداد")),
                ("purchase_date", models.DateField(blank=True, null=True, verbose_name="تاریخ تحویل")),
                ("value", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="ارزش")),
                ("note", models.TextField(blank=True, default="", verbose_name="توضیحات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tools",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "ابزار نجاری (بتا)",
                "verbose_name_plural": "ابزارهای نجاری (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCarpentryWoodPurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد خرید")),
                ("supplier", models.CharField(blank=True, default="", max_length=150, verbose_name="تامین‌کننده")),
                ("material_type", models.CharField(blank=True, default="", max_length=80, verbose_name="نوع متریال")),
                ("wood_type", models.CharField(blank=True, default="", max_length=80, verbose_name="جنس چوب")),
                ("quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14, verbose_name="مقدار")),
                ("unit", models.CharField(blank=True, default="متر", max_length=20, verbose_name="واحد")),
                ("unit_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="بهای واحد")),
                ("total_cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="مبلغ کل")),
                ("purchase_date", models.DateField(blank=True, null=True, verbose_name="تاریخ خرید")),
                ("invoice_ref", models.CharField(blank=True, default="", max_length=80, verbose_name="شماره فاکتور")),
                ("note", models.TextField(blank=True, default="", verbose_name="توضیحات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wood_purchases",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "خرید چوب نجاری (بتا)",
                "verbose_name_plural": "خریدهای چوب نجاری (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCarpentryExternalService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد خدمت")),
                ("service_type", models.CharField(blank=True, default="", max_length=80, verbose_name="نوع خدمت")),
                ("provider", models.CharField(blank=True, default="", max_length=150, verbose_name="پیمانکار / ارائه‌دهنده")),
                ("amount", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="مبلغ")),
                ("service_date", models.DateField(blank=True, null=True, verbose_name="تاریخ")),
                ("description", models.TextField(blank=True, default="", verbose_name="شرح")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "carpentry_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_services",
                        to="backend.betacarpentryorder",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_services",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "خدمت برون‌سازمانی نجاری (بتا)",
                "verbose_name_plural": "خدمات برون‌سازمانی نجاری (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCarpentryFreight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد حمل")),
                ("destination", models.CharField(blank=True, default="", max_length=150, verbose_name="مقصد")),
                ("driver_name", models.CharField(blank=True, default="", max_length=120, verbose_name="راننده / باربری")),
                ("cost", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="هزینه")),
                ("sent_date", models.DateField(blank=True, null=True, verbose_name="تاریخ ارسال")),
                ("note", models.TextField(blank=True, default="", verbose_name="توضیحات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "carpentry_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="freight_records",
                        to="backend.betacarpentryorder",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="freight_records",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "باربری نجاری (بتا)",
                "verbose_name_plural": "باربری‌های نجاری (بتا)",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="BetaCarpentryAttendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("person_name", models.CharField(max_length=120, verbose_name="نام پرسنل")),
                ("visit_date", models.DateField(verbose_name="تاریخ")),
                ("check_in", models.TimeField(blank=True, null=True, verbose_name="ورود")),
                ("check_out", models.TimeField(blank=True, null=True, verbose_name="خروج")),
                ("note", models.TextField(blank=True, default="", verbose_name="توضیحات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workshop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_records",
                        to="backend.betacarpentryworkshop",
                    ),
                ),
            ],
            options={
                "verbose_name": "تردد نجاری (بتا)",
                "verbose_name_plural": "ترددهای نجاری (بتا)",
                "ordering": ["-visit_date", "-id"],
            },
        ),
    ]
