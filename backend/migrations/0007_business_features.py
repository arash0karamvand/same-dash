# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def clear_attendance(apps, schema_editor):
    StaffAttendance = apps.get_model("backend", "StaffAttendance")
    StaffAttendance.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0006_staff_attendance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Seller",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("full_name", models.CharField(max_length=150, verbose_name="نام کامل")),
                ("branch", models.CharField(choices=[("branch_1", "شعبه ۱"), ("branch_2", "شعبه ۲")], default="branch_1", max_length=20, verbose_name="شعبه")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="موبایل")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")),
                ("user", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="seller_profile", to=settings.AUTH_USER_MODEL, verbose_name="حساب ورود")),
            ],
            options={
                "verbose_name": "فروشنده",
                "verbose_name_plural": "فروشندگان",
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=150, verbose_name="نام محصول")),
                ("default_price", models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="قیمت پیش‌فرض")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")),
            ],
            options={
                "verbose_name": "محصول",
                "verbose_name_plural": "محصولات",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("create", "ایجاد"), ("update", "ویرایش"), ("delete", "حذف"), ("approve", "تایید"), ("reject", "رد"), ("sale", "فروش"), ("check_in", "ثبت حضور"), ("login", "ورود")], max_length=20, verbose_name="عملیات")),
                ("entity_type", models.CharField(blank=True, max_length=50, verbose_name="نوع موجودیت")),
                ("entity_id", models.CharField(blank=True, max_length=50, verbose_name="شناسه")),
                ("message", models.CharField(max_length=500, verbose_name="شرح")),
                ("details", models.JSONField(blank=True, default=dict, verbose_name="جزئیات")),
                ("is_executive_only", models.BooleanField(default=False, verbose_name="فقط مدیر ارشد")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL, verbose_name="کاربر")),
            ],
            options={
                "verbose_name": "لاگ فعالیت",
                "verbose_name_plural": "لاگ‌های فعالیت",
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(clear_attendance, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="staffattendance",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="staffattendance",
            name="employee",
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="seller",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance", to="backend.seller", verbose_name="فروشنده"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="approval_status",
            field=models.CharField(choices=[("pending", "در انتظار تایید"), ("approved", "تایید شده"), ("rejected", "رد شده")], default="approved", max_length=12, verbose_name="وضعیت تایید"),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="work_branch",
            field=models.CharField(blank=True, choices=[("branch_1", "شعبه ۱"), ("branch_2", "شعبه ۲")], max_length=20, verbose_name="شعبه کاری"),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_attendance", to=settings.AUTH_USER_MODEL, verbose_name="تاییدکننده"),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاریخ تایید"),
        ),
        migrations.AlterUniqueTogether(
            name="staffattendance",
            unique_together={("seller", "date")},
        ),
        migrations.AddField(
            model_name="sale",
            name="branch",
            field=models.CharField(blank=True, choices=[("branch_1", "شعبه ۱"), ("branch_2", "شعبه ۲")], max_length=20, verbose_name="شعبه"),
        ),
        migrations.AddField(
            model_name="sale",
            name="seller",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sales", to="backend.seller", verbose_name="فروشنده"),
        ),
        migrations.CreateModel(
            name="SaleLineItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=150, verbose_name="نام محصول")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="تعداد")),
                ("unit_price", models.DecimalField(decimal_places=0, max_digits=18, verbose_name="قیمت واحد")),
                ("line_total", models.DecimalField(decimal_places=0, max_digits=18, verbose_name="جمع ردیف")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sale_lines", to="backend.product", verbose_name="محصول")),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="line_items", to="backend.sale", verbose_name="فروش")),
            ],
            options={
                "verbose_name": "ردیف فروش",
                "verbose_name_plural": "ردیف‌های فروش",
            },
        ),
    ]
