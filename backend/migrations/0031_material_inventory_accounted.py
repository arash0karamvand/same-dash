from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0030_material_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="inventory_accounted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="ثبت حسابداری موجودی"),
        ),
    ]
