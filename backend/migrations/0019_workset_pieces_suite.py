from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0018_furniture_worksets"),
    ]

    operations = [
        migrations.CreateModel(
            name="FurnitureWorksetPiece",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("piece_kind", models.CharField(max_length=32, verbose_name="نوع قطعه")),
                ("arm_style", models.CharField(max_length=16, verbose_name="حالت دسته")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="تعداد")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
                (
                    "workset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pieces",
                        to="backend.furnitureworkset",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="furnitureworksetpiece",
            constraint=models.UniqueConstraint(
                fields=("workset", "piece_kind", "arm_style"),
                name="uq_workset_piece_arm",
            ),
        ),
        migrations.AddConstraint(
            model_name="furnitureworksetpiece",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ck_workset_piece_qty",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="furniture_workset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="backend.furnitureworkset",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="suite_config",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
