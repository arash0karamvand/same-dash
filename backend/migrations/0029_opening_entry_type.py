from django.db import migrations


def add_opening_type(apps, schema_editor):
    JournalEntryType = apps.get_model("backend", "JournalEntryType")
    JournalEntryType.objects.update_or_create(
        code="opening",
        defaults={"label": "افتتاحیه / تراز وارداتی", "sort_order": 7, "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0028_accounting_origin"),
    ]

    operations = [
        migrations.RunPython(add_opening_type, migrations.RunPython.noop),
    ]
