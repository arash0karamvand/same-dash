from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0008_delivery_ready_freight"),
    ]

    operations = [
        migrations.AddField(
            model_name="remindercampaign",
            name="rfm_segments",
            field=models.ManyToManyField(
                blank=True,
                related_name="reminder_campaigns",
                to="backend.rfmsegment",
            ),
        ),
        migrations.AddField(
            model_name="rfmactionlog",
            name="previous_segment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="previous_action_logs",
                to="backend.rfmsegment",
            ),
        ),
    ]
