# Generated manually — کد حساب کل، معین، تفصیلی و فیلدهای سند

from django.db import migrations, models
import django.db.models.deletion


ACCOUNT_CODES = {
    "cash_documents": "1120",
    "petty_cash": "1130",
    "bank": "1210",
    "collection_at_bank": "1220",
    "receivables": "1310",
    "other_receivables": "1320",
    "raw_materials_inventory": "1510",
    "wip_inventory": "1520",
    "semi_finished_inventory": "1530",
    "finished_goods_inventory": "1540",
    "prepayments": "1710",
    "investment_projects": "1740",
    "deposits_sureties": "1750",
    "bank_payables": "4110",
    "accounts_payable": "4311",
    "other_payables": "4321",
    "long_term_loans": "5110",
    "retained_earnings": "6320",
    "raw_materials_sales": "7210",
    "semi_finished_sales": "7230",
    "product_sales": "7240",
    "other_revenue": "7510",
    "purchase_discount": "7520",
    "production_payroll": "8110",
    "production_overhead": "8111",
    "admin_payroll": "8210",
    "admin_overhead": "8211",
    "distribution_sales_expense": "8220",
    "financial_expense": "8310",
    "raw_materials_purchase_return": "9430",
    "memorandum_accounts": "9710",
    "memorandum_counterpart": "9720",
    "raw_materials_purchase_return_cogs": "9930",
}


def backfill_account_codes(apps, schema_editor):
    Account = apps.get_model("backend", "Account")
    for slug, code in ACCOUNT_CODES.items():
        Account.objects.filter(slug=slug).update(code=code)


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0031_material_inventory_accounted"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="code",
            field=models.CharField(blank=True, db_index=True, max_length=10, verbose_name="کد حساب کل"),
        ),
        migrations.CreateModel(
            name="SubsidiaryAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=10, verbose_name="کد معین")),
                ("name", models.CharField(max_length=120, verbose_name="عنوان حساب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subsidiaries",
                        to="backend.account",
                        verbose_name="حساب کل",
                    ),
                ),
            ],
            options={
                "verbose_name": "حساب معین",
                "verbose_name_plural": "حساب‌های معین",
                "ordering": ["account__sort_order", "code"],
            },
        ),
        migrations.CreateModel(
            name="DetailedAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=10, verbose_name="کد تفصیلی")),
                ("name", models.CharField(max_length=120, verbose_name="عنوان حساب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                (
                    "subsidiary",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="details",
                        to="backend.subsidiaryaccount",
                        verbose_name="حساب معین",
                    ),
                ),
            ],
            options={
                "verbose_name": "حساب تفصیلی",
                "verbose_name_plural": "حساب‌های تفصیلی",
                "ordering": ["subsidiary__account__sort_order", "subsidiary__code", "code"],
            },
        ),
        migrations.AddConstraint(
            model_name="subsidiaryaccount",
            constraint=models.UniqueConstraint(fields=("account", "code"), name="uniq_subsidiary_account_code"),
        ),
        migrations.AddConstraint(
            model_name="detailedaccount",
            constraint=models.UniqueConstraint(fields=("subsidiary", "code"), name="uniq_detailed_account_code"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="attach_code",
            field=models.CharField(blank=True, max_length=10, verbose_name="ع"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="document_number",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name="شماره سند"),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="detailed",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="backend.detailedaccount",
                verbose_name="حساب تفصیلی",
            ),
        ),
        migrations.AddField(
            model_name="accountingentry",
            name="subsidiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="backend.subsidiaryaccount",
                verbose_name="حساب معین",
            ),
        ),
        migrations.RunPython(backfill_account_codes, migrations.RunPython.noop),
    ]
