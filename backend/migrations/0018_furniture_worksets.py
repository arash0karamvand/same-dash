from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0017_receive_kinds_pipeline"),
    ]

    operations = [
        migrations.CreateModel(
            name="FurnitureWorkset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("name", models.CharField(max_length=150, verbose_name="نام دست")),
                ("design_style", models.CharField(blank=True, default="", max_length=32, verbose_name="سبک طراحی")),
                ("seat_count", models.PositiveIntegerField(blank=True, null=True, verbose_name="تعداد نفر")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="frame",
            name="workset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="frames",
                to="backend.furnitureworkset",
            ),
        ),
        migrations.AddField(
            model_name="frame",
            name="piece_kind",
            field=models.CharField(blank=True, default="", max_length=32, verbose_name="نوع قطعه"),
        ),
        migrations.AddField(
            model_name="frame",
            name="arm_style",
            field=models.CharField(blank=True, default="", max_length=16, verbose_name="حالت دسته"),
        ),
        migrations.AddField(
            model_name="sale",
            name="seat_count",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="تعداد نفر"),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="furniture_workset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_lines",
                to="backend.furnitureworkset",
            ),
        ),
    ]
