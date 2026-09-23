"""Create structural ledgers only; chart accounts come from uploaded Excel."""

from django.db import migrations


def create_ledgers(apps, schema_editor):
    Ledger = apps.get_model("backend", "Ledger")
    for code, name, kind in (
        ("office", "اداری", "office"),
        ("factory", "کارخانه", "factory"),
    ):
        Ledger.objects.update_or_create(
            code=code,
            defaults={"name": name, "kind": kind, "is_active": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_ledgers, migrations.RunPython.noop),
    ]
