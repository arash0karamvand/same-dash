from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0020_paint_recipe_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshoprecipe",
            name="fabric_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("velvet_plain", "مخمل ساده"),
                    ("velvet_pattern", "مخمل طرح‌دار"),
                    ("washed_cotton", "کتان شست"),
                    ("heavy_linen", "لینن ضخیم"),
                    ("matte_leather", "چرم مصنوعی مات"),
                    ("soft_suede", "جیر نرم"),
                    ("loop_weave", "بافت حلقه‌ای"),
                    ("stretch_cloth", "پارچه کشسان"),
                    ("matte_satin", "ساتن مات"),
                    ("outdoor_cloth", "پارچه فضای باز"),
                ],
                default="",
                max_length=40,
                verbose_name="دسته‌بندی پارچه",
            ),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="company_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("nura_weave", "بافندگی نورا"),
                    ("aria_textile", "منسوجات آریا"),
                    ("sepehr_hide", "چرمینه سپهر"),
                    ("roshan_line", "کالکشن روشان"),
                ],
                default="",
                max_length=40,
                verbose_name="شرکت پارچه",
            ),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="origin_country",
            field=models.CharField(blank=True, default="", max_length=40, verbose_name="کشور سازنده"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="roll_count",
            field=models.PositiveIntegerField(default=1, verbose_name="تعداد طاقه"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="image_url",
            field=models.URLField(blank=True, default="", verbose_name="تصویر کالیته"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="gallery_urls",
            field=models.JSONField(blank=True, default=list, verbose_name="گالری تصاویر"),
        ),
        migrations.AddConstraint(
            model_name="workshoprecipe",
            constraint=models.CheckConstraint(
                condition=models.Q(("roll_count__gte", 0)),
                name="ck_workshop_recipe_roll_count",
            ),
        ),
    ]
