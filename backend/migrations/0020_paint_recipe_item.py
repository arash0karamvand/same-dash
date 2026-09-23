from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0019_workset_pieces_suite"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshoprecipe",
            name="item_code",
            field=models.CharField(blank=True, max_length=40, null=True, unique=True, verbose_name="کد رهگیری"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="paint_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("thinner", "تینر"),
                    ("paint", "رنگ و پلی‌استر"),
                    ("putty", "بتونه و سیلر"),
                    ("patina", "پتینه و ورق طلا"),
                    ("abrasive", "سنباده و ابزار مصرفی"),
                    ("chemical", "هاردنر و شیمیایی"),
                ],
                default="",
                max_length=20,
                verbose_name="دسته‌بندی رنگ",
            ),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="brand",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="برند"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="stock_unit",
            field=models.CharField(blank=True, default="", max_length=20, verbose_name="واحد شمارش"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="current_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=18, verbose_name="موجودی"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="min_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=18, verbose_name="نقطه سفارش"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="storage_shelf",
            field=models.CharField(blank=True, default="", max_length=80, verbose_name="موقعیت قفسه"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="unit_cost",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=18, verbose_name="نرخ واحد"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="technical_specs",
            field=models.TextField(blank=True, default="", verbose_name="مشخصات فنی"),
        ),
        migrations.AddConstraint(
            model_name="workshoprecipe",
            constraint=models.CheckConstraint(
                condition=models.Q(("current_stock__gte", 0)),
                name="ck_workshop_recipe_stock",
            ),
        ),
        migrations.AddConstraint(
            model_name="workshoprecipe",
            constraint=models.CheckConstraint(
                condition=models.Q(("min_stock__gte", 0)),
                name="ck_workshop_recipe_min_stock",
            ),
        ),
        migrations.AddConstraint(
            model_name="workshoprecipe",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_cost__gte", 0)),
                name="ck_workshop_recipe_unit_cost",
            ),
        ),
    ]
