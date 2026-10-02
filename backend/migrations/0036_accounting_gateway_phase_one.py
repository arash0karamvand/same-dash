import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


DEFAULT_RULES = {
    "sale": [
        ("credit", "product_sales"),
        ("debit", "receivables"),
    ],
    "payment": [("credit", "receivables")],
    "check_register": [("credit", "receivables")],
    "material_receipt": [
        ("debit", "raw_materials_inventory"),
        ("credit", "accounts_payable"),
    ],
    "material_consumption": [
        ("debit", "wip_inventory"),
        ("credit", "raw_materials_inventory"),
    ],
    "material_consumption_reverse": [
        ("debit", "raw_materials_inventory"),
        ("credit", "wip_inventory"),
    ],
    "goods_sale_issue": [
        ("debit", "cogs"),
        ("credit", "finished_goods_inventory"),
    ],
    "goods_sale_issue_reverse": [
        ("debit", "finished_goods_inventory"),
        ("credit", "cogs"),
    ],
}


def seed_posting_mappings(apps, schema_editor):
    Account = apps.get_model("backend", "Account")
    LookupOption = apps.get_model("backend", "LookupOption")
    Mapping = apps.get_model("backend", "PostingAccountMapping")
    rules = {key: list(value) for key, value in DEFAULT_RULES.items()}
    for option in LookupOption.objects.filter(category="posting_rule", is_active=True):
        lines = (option.meta or {}).get("lines") or []
        parsed = [
            (line.get("side"), line.get("slug"))
            for line in lines
            if line.get("side") in {"debit", "credit"} and line.get("slug")
        ]
        if parsed:
            rules[option.code] = parsed
    for ledger_id in Account.objects.values_list("ledger_id", flat=True).distinct():
        for event_key, lines in rules.items():
            for side, slug in lines:
                account = Account.objects.filter(
                    ledger_id=ledger_id,
                    slug=slug,
                    is_active=True,
                ).first()
                if account is None or Account.objects.filter(parent_id=account.id).exists():
                    continue
                Mapping.objects.get_or_create(
                    ledger_id=ledger_id,
                    event_key=event_key,
                    role=slug,
                    side=side,
                    context_key="||",
                    effective_from=django.utils.timezone.localdate(),
                    defaults={
                        "account_id": account.id,
                        "priority": -100,
                        "metadata": {"seeded_from": "legacy_posting_rule", "fallback_slug": slug},
                    },
                )


class Migration(migrations.Migration):
    dependencies = [("backend", "0035_crm_workbook")]

    operations = [
        migrations.CreateModel(
            name="AccountingSourceReference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_module", models.CharField(max_length=40)),
                ("source_type", models.CharField(max_length=80)),
                ("source_uuid", models.UUIDField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["source_module", "source_type", "source_uuid"]},
        ),
        migrations.CreateModel(
            name="PostingAccountMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.SlugField(max_length=80)),
                ("role", models.SlugField(max_length=80)),
                ("side", models.CharField(choices=[("debit", "بدهکار"), ("credit", "بستانکار")], max_length=10)),
                ("item_category", models.CharField(blank=True, default="", max_length=80)),
                ("context_key", models.CharField(default="", editable=False, max_length=220)),
                ("effective_from", models.DateField(default=django.utils.timezone.localdate)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.SmallIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="posting_mappings", to="backend.account")),
                ("branch", models.ForeignKey(blank=True, db_column="branch", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="posting_account_mappings", to="backend.branch", to_field="code")),
                ("ledger", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="posting_mappings", to="backend.ledger")),
                ("warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="posting_account_mappings", to="backend.warehouse")),
            ],
            options={"ordering": ["event_key", "role", "-priority", "-effective_from", "id"]},
        ),
        migrations.AddField(
            model_name="financialevent",
            name="source_reference",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="financial_events", to="backend.accountingsourcereference"),
        ),
        migrations.AlterField(
            model_name="transactionsource",
            name="origin",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="transaction_links", to="backend.accountingorigin"),
        ),
        migrations.AddField(
            model_name="transactionsource",
            name="source_reference",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="transaction_links", to="backend.accountingsourcereference"),
        ),
        migrations.AddConstraint(
            model_name="accountingsourcereference",
            constraint=models.UniqueConstraint(fields=("source_type", "source_uuid"), name="uq_account_source_type_uuid"),
        ),
        migrations.AddConstraint(
            model_name="accountingsourcereference",
            constraint=models.CheckConstraint(condition=~models.Q(source_module=""), name="ck_account_source_module"),
        ),
        migrations.AddConstraint(
            model_name="accountingsourcereference",
            constraint=models.CheckConstraint(condition=~models.Q(source_type=""), name="ck_account_source_type"),
        ),
        migrations.AddIndex(
            model_name="accountingsourcereference",
            index=models.Index(fields=["source_module", "source_type"], name="ix_account_source_kind"),
        ),
        migrations.AddConstraint(
            model_name="postingaccountmapping",
            constraint=models.UniqueConstraint(fields=("ledger", "event_key", "role", "side", "context_key", "effective_from"), name="uq_post_map_context_date"),
        ),
        migrations.AddConstraint(
            model_name="postingaccountmapping",
            constraint=models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_post_map_dates"),
        ),
        migrations.AddIndex(
            model_name="postingaccountmapping",
            index=models.Index(fields=["ledger", "event_key", "role", "side", "is_active"], name="ix_post_map_lookup"),
        ),
        migrations.AddConstraint(
            model_name="transactionsource",
            constraint=models.UniqueConstraint(fields=("transaction", "source_reference"), name="uq_tx_source_reference"),
        ),
        migrations.AddConstraint(
            model_name="transactionsource",
            constraint=models.CheckConstraint(
                condition=models.Q(origin__isnull=False, source_reference__isnull=True)
                | models.Q(origin__isnull=True, source_reference__isnull=False),
                name="ck_tx_source_one_reference",
            ),
        ),
        migrations.RunPython(seed_posting_mappings, migrations.RunPython.noop),
    ]
