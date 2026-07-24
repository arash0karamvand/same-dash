# Generated manually for accounting chart of accounts

from django.db import migrations, models
import django.db.models.deletion


def seed_chart_and_backfill(apps, schema_editor):
    from logic.accounting_accounts import CHART_OF_ACCOUNTS, ENTRY_TYPE_ACCOUNT_SLUGS

    Account = apps.get_model("backend", "Account")
    AccountingEntry = apps.get_model("backend", "AccountingEntry")

    for row in CHART_OF_ACCOUNTS:
        defaults = {
            "name": row["name"],
            "account_class": row["account_class"],
            "normal_balance": row["normal_balance"],
            "sort_order": row["sort_order"],
            "legacy_entry_type": row.get("legacy_entry_type", ""),
            "is_active": True,
        }
        Account.objects.update_or_create(slug=row["slug"], defaults=defaults)

    slug_by_entry_type = dict(ENTRY_TYPE_ACCOUNT_SLUGS)
    for entry in AccountingEntry.objects.filter(account__isnull=True).iterator():
        slug = slug_by_entry_type.get(entry.entry_type, "other_revenue")
        account = Account.objects.filter(slug=slug).first()
        if account:
            entry.account_id = account.id
            entry.save(update_fields=["account_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0023_workflow_separate_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=60, unique=True, verbose_name="شناسه")),
                ("name", models.CharField(max_length=120, verbose_name="نام حساب")),
                (
                    "account_class",
                    models.CharField(
                        choices=[
                            ("asset", "دارایی"),
                            ("liability", "بدهی"),
                            ("equity", "حقوق صاحبان سهام"),
                            ("revenue", "درآمد"),
                            ("expense", "هزینه"),
                        ],
                        max_length=20,
                        verbose_name="طبقه",
                    ),
                ),
                (
                    "normal_balance",
                    models.CharField(
                        choices=[("debit", "بدهکار"), ("credit", "بستانکار")],
                        max_length=10,
                        verbose_name="ماهیت",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="ترتیب")),
                ("legacy_entry_type", models.CharField(blank=True, max_length=20, verbose_name="نوع سند قدیمی")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
            ],
            options={
                "verbose_name": "حساب",
                "verbose_name_plural": "حساب‌ها",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="backend.account",
                verbose_name="حساب",
            ),
        ),
        migrations.RunPython(seed_chart_and_backfill, migrations.RunPython.noop),
    ]
