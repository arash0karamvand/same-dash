from django.db import migrations, models


def seed_fabric_catalog(apps, schema_editor):
    Node = apps.get_model("backend", "FabricCatalogNode")
    countries = ["ایران", "ترکیه", "چین", "ایتالیا", "هند", "اسپانیا"]
    brands = {
        "ایران": ["بافندگی نورا", "منسوجات آریا"],
        "ترکیه": ["چرمینه سپهر"],
        "ایتالیا": ["کالکشن روشان"],
    }
    colors = ["استخوانی", "دودی", "کرم"]
    cloths = ["مخمل ساده", "کتان شست", "جیر نرم"]
    for country_name in countries:
        country = Node.objects.create(kind="country", name=country_name)
        for brand_name in brands.get(country_name, []):
            brand = Node.objects.create(kind="brand", name=brand_name, parent=country)
            for color_name in colors:
                color = Node.objects.create(kind="color", name=color_name, parent=brand)
                for cloth_name in cloths:
                    Node.objects.create(kind="type", name=cloth_name, parent=color)


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0021_fabric_calite"),
    ]

    operations = [
        migrations.CreateModel(
            name="FabricCatalogNode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("country", "کشور"), ("brand", "برند"), ("color", "رنگ"), ("type", "جنس")], db_index=True, max_length=20, verbose_name="نوع")),
                ("name", models.CharField(max_length=80, verbose_name="نام")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="children", to="backend.fabriccatalognode")),
            ],
            options={
                "verbose_name": "گره کاتالوگ پارچه",
                "verbose_name_plural": "گره‌های کاتالوگ پارچه",
                "ordering": ["kind", "name", "id"],
            },
        ),
        migrations.RunPython(seed_fabric_catalog, migrations.RunPython.noop),
        migrations.AddField(
            model_name="workshoprecipe",
            name="fabric_country",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="country_recipes", to="backend.fabriccatalognode"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="fabric_brand",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="brand_recipes", to="backend.fabriccatalognode"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="fabric_color",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="color_recipes", to="backend.fabriccatalognode"),
        ),
        migrations.AddField(
            model_name="workshoprecipe",
            name="fabric_type",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="type_recipes", to="backend.fabriccatalognode"),
        ),
        migrations.AlterField(
            model_name="workshoprecipe",
            name="image_url",
            field=models.TextField(blank=True, default="", verbose_name="تصویر کالیته"),
        ),
    ]
