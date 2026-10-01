from django.db import migrations, models


def rename_satellite_workshop(apps, schema_editor):
    LookupOption = apps.get_model("backend", "LookupOption")
    LookupOption.objects.filter(category="beta_workshop_kind", code="satellite").update(label="بازرگان")
    Workshop = apps.get_model("backend", "BetaCarpentryWorkshop")
    Workshop.objects.filter(kind="satellite", service_flow="").update(service_flow="both")


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0030_unified_accounting_core"),
    ]

    operations = [
        migrations.AddField(
            model_name="betacarpentryworkshop",
            name="service_flow",
            field=models.CharField(blank=True, default="", max_length=16, verbose_name="جهت سرویس"),
        ),
        migrations.RunPython(rename_satellite_workshop, migrations.RunPython.noop),
    ]
