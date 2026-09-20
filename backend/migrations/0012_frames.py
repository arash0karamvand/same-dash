import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0011_leave_mission_dispatch"),
    ]

    operations = [
        migrations.CreateModel(
            name="Frame",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(db_index=True, default=False, verbose_name="حذف‌شده")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="تاریخ حذف")),
                ("name", models.CharField(max_length=150, verbose_name="نام کلاف")),
                (
                    "design_style",
                    models.CharField(
                        choices=[
                            ("modern", "مدرن"),
                            ("classic", "کلاسیک"),
                            ("neo_classic", "نیو کلاسیک"),
                            ("minimal", "مینیمال"),
                            ("avant_garde", "اوانگارد"),
                        ],
                        default="modern",
                        max_length=32,
                        verbose_name="سبک طراحی",
                    ),
                ),
                (
                    "wood_type",
                    models.CharField(
                        choices=[
                            ("ash_georgian_g1", "راش گرجستان درجه ۱"),
                            ("oak", "بلوط"),
                            ("walnut", "گردو"),
                            ("russian", "روس"),
                            ("tusca", "توسکا"),
                            ("ash_russian_mix", "ترکیب راش و روس"),
                        ],
                        default="ash_georgian_g1",
                        max_length=32,
                        verbose_name="جنس چوب اصلی",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="frames",
                        to="backend.product",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="FrameModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="نام مدل")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                (
                    "frame",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="models",
                        to="backend.frame",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="FrameServiceTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="سرویس ۸ نفره", max_length=100, verbose_name="نام سرویس")),
                ("default_seat_count", models.PositiveIntegerField(default=8, verbose_name="تعداد نفر پیش‌فرض")),
                (
                    "frame",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_template",
                        to="backend.frame",
                    ),
                ),
            ],
            options={
                "ordering": ["frame_id"],
            },
        ),
        migrations.CreateModel(
            name="FrameServiceComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "component_type",
                    models.CharField(
                        choices=[
                            ("three_seater", "کاناپه ۳ نفره"),
                            ("armchair", "مبل تک‌نفره"),
                            ("side_table", "کنار مبل"),
                            ("coffee_table", "جلو مبل"),
                        ],
                        max_length=32,
                        verbose_name="نوع قطعه",
                    ),
                ),
                ("default_quantity", models.PositiveIntegerField(default=1, verbose_name="تعداد پیش‌فرض")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="components",
                        to="backend.frameservicetemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="FrameWoodRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(blank=True, max_length=100, verbose_name="برچسب")),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=18, verbose_name="مقدار")),
                (
                    "unit",
                    models.CharField(
                        choices=[("متر", "متر"), ("عدد", "عدد")],
                        default="متر",
                        max_length=20,
                        verbose_name="واحد",
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "frame_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wood_requirements",
                        to="backend.framemodel",
                    ),
                ),
                (
                    "material",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="frame_wood_requirements",
                        to="backend.material",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="FrameComponentMaterialRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "rule_key",
                    models.CharField(
                        choices=[
                            ("back_fabric", "پشت پارچه"),
                            ("back_wood", "پشت چوب"),
                            ("extra", "متریال اضافه"),
                        ],
                        max_length=32,
                        verbose_name="نوع قانون",
                    ),
                ),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=18, verbose_name="مقدار")),
                ("unit", models.CharField(default="متر", max_length=20, verbose_name="واحد")),
                ("is_default", models.BooleanField(default=False, verbose_name="پیش‌فرض")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="material_rules",
                        to="backend.frameservicecomponent",
                    ),
                ),
                (
                    "material",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="frame_component_rules",
                        to="backend.material",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="frame",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="linked_products",
                to="backend.frame",
            ),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="frame",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_lines",
                to="backend.frame",
            ),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="frame_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_lines",
                to="backend.framemodel",
            ),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="frame_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddConstraint(
            model_name="framemodel",
            constraint=models.UniqueConstraint(fields=("frame", "name"), name="uq_frame_model_name"),
        ),
        migrations.AddConstraint(
            model_name="frameservicecomponent",
            constraint=models.UniqueConstraint(
                fields=("template", "component_type"),
                name="uq_frame_service_component_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="framewoodrequirement",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_frame_wood_qty"),
        ),
        migrations.AddConstraint(
            model_name="framecomponentmaterialrule",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_frame_rule_qty"),
        ),
    ]
