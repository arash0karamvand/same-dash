import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0013_beta_workshops"),
    ]

    operations = [
        migrations.AddField(
            model_name="betacarpentryorder",
            name="frame",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="beta_carpentry_orders",
                to="backend.frame",
                verbose_name="کلاف",
            ),
        ),
    ]
