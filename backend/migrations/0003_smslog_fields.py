# Generated manually for SMSLog field updates

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0002_alter_smslog_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="smslog",
            old_name="phone",
            new_name="phone_number",
        ),
        migrations.RenameField(
            model_name="smslog",
            old_name="error",
            new_name="error_message",
        ),
        migrations.AddField(
            model_name="smslog",
            name="provider_response",
            field=models.TextField(blank=True, verbose_name="پاسخ درگاه"),
        ),
        migrations.AddField(
            model_name="smslog",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sms_logs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ارسال‌کننده",
            ),
        ),
    ]
