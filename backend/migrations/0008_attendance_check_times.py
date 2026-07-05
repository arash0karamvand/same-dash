# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0007_business_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffattendance",
            name="check_in_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="زمان ورود"),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="check_out_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="زمان پایان کار"),
        ),
    ]
