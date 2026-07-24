# Backfill document codes for existing entries

from django.db import migrations


def backfill_document_codes(apps, schema_editor):
    AccountingEntry = apps.get_model("backend", "AccountingEntry")
    for entry in AccountingEntry.objects.filter(document_code="").order_by("id"):
        entry.document_code = f"S-{entry.id:05d}"
        entry.save(update_fields=["document_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0025_accounting_entry_document_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_document_codes, migrations.RunPython.noop),
    ]
