from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0014_remove_legacy_builtin_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="address",
            field=models.TextField(blank=True, verbose_name="آدرس"),
        ),
        migrations.AddField(
            model_name="product",
            name="fabric",
            field=models.CharField(blank=True, max_length=100, verbose_name="پارچه"),
        ),
        migrations.AddField(
            model_name="product",
            name="product_model",
            field=models.CharField(blank=True, max_length=100, verbose_name="مدل"),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="fabric",
            field=models.CharField(blank=True, max_length=100, verbose_name="پارچه"),
        ),
        migrations.AddField(
            model_name="salelineitem",
            name="product_model",
            field=models.CharField(blank=True, max_length=100, verbose_name="مدل"),
        ),
    ]
