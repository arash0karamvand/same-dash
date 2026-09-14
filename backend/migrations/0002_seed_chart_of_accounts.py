"""Seed full 33-account Iranian chart of accounts into office and factory ledgers."""

from django.db import migrations


def seed_full_chart(apps, schema_editor):
    from logic.accounting_accounts import seed_accounts
    from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

    seed_accounts(ledger=OFFICE_LEDGER)
    seed_accounts(ledger=FACTORY_LEDGER)


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_full_chart, migrations.RunPython.noop),
    ]
