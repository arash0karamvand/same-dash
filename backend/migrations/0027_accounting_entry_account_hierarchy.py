# حساب کل، معین و تفصیلی برای هر سند

from django.db import migrations, models


def backfill_account_hierarchy(apps, schema_editor):
    AccountingEntry = apps.get_model("backend", "AccountingEntry")
    class_labels = {
        "asset": "دارایی",
        "liability": "بدهی",
        "equity": "حقوق صاحبان سهام",
        "revenue": "درآمد",
        "expense": "هزینه",
    }
    for entry in AccountingEntry.objects.select_related("account").iterator():
        if not entry.account_id:
            continue
        account = entry.account
        updates = {}
        if not entry.general_account:
            updates["general_account"] = class_labels.get(account.account_class, account.account_class)
        if not entry.subsidiary_account:
            updates["subsidiary_account"] = account.name
        if updates:
            AccountingEntry.objects.filter(pk=entry.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0026_backfill_document_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountingentry",
            name="general_account",
            field=models.CharField(blank=True, max_length=120, verbose_name="حساب کل"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="subsidiary_account",
            field=models.CharField(blank=True, max_length=120, verbose_name="حساب معین"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="detailed_account",
            field=models.CharField(blank=True, max_length=120, verbose_name="حساب تفصیلی"),
        ),
        migrations.RunPython(backfill_account_hierarchy, migrations.RunPython.noop),
    ]
