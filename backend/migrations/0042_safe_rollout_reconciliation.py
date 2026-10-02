import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


ACCOUNT_ROLES = {
    "1120": "cash_documents", "1130": "petty_cash", "1210": "bank",
    "1220": "collection_at_bank", "1310": "receivables",
    "1320": "other_receivables", "1330": "vat_receivable",
    "1510": "raw_materials_inventory", "1520": "wip_inventory",
    "1530": "semi_finished_inventory", "1540": "finished_goods_inventory",
    "1710": "prepayments", "1740": "investment_projects",
    "1750": "deposits_sureties", "4110": "bank_payables",
    "4311": "accounts_payable", "4321": "other_payables",
    "4330": "vat_payable", "5110": "long_term_loans",
    "6320": "retained_earnings", "7210": "raw_materials_sales",
    "7230": "semi_finished_sales", "7240": "product_sales",
    "7250": "sales_allowances", "7510": "other_revenue",
    "7520": "purchase_discount", "8110": "production_payroll",
    "8111": "production_overhead", "8112": "cogs",
    "8210": "admin_payroll", "8211": "admin_overhead",
    "8220": "distribution_sales_expense", "8310": "financial_expense",
    "9430": "raw_materials_purchase_return", "9710": "memorandum_accounts",
    "9720": "memorandum_counterpart",
    "9930": "raw_materials_purchase_return_cogs",
}
CLASS_BY_PREFIX = {
    "1": "asset", "4": "liability", "5": "liability", "6": "equity",
    "7": "revenue", "8": "expense", "9": "expense",
}
def _queue(Queue, domain, source_type, source_key, reason, details=None):
    Queue.objects.get_or_create(
        domain=domain,
        source_type=source_type,
        source_key=str(source_key),
        reason=reason,
        defaults={"details": details or {}},
    )


def safe_backfill(apps, schema_editor):
    Queue = apps.get_model("backend", "ReconciliationQueue")
    Movement = apps.get_model("backend", "InventoryTransaction")
    Layer = apps.get_model("backend", "InventoryCostLayer")
    Consumption = apps.get_model("backend", "InventoryConsumption")
    ProductMaterial = apps.get_model("backend", "ProductMaterial")
    BOMVersion = apps.get_model("backend", "BOMVersion")
    BOMLine = apps.get_model("backend", "BOMLine")
    SaleLine = apps.get_model("backend", "SaleLineItem")
    Plan = apps.get_model("backend", "FulfillmentPlan")
    Event = apps.get_model("backend", "FinancialEvent")
    SourceReference = apps.get_model("backend", "AccountingSourceReference")
    TransactionSource = apps.get_model("backend", "TransactionSource")
    Ledger = apps.get_model("backend", "Ledger")
    Account = apps.get_model("backend", "Account")

    # Fresh installs need the canonical system roles before automatic posting
    # can be enabled. Exact standard codes are deterministic; conflicting
    # imported codes are queued instead of being relabelled.
    office = Ledger.objects.filter(code="office").first()
    if office:
        for sort_order, (code, slug) in enumerate(ACCOUNT_ROLES.items(), 1):
            if Account.objects.filter(ledger_id=office.pk, slug=slug).exists():
                continue
            conflicting = Account.objects.filter(
                ledger_id=office.pk, parent_id=None, code=code
            ).first()
            if conflicting:
                _queue(
                    Queue,
                    "accounting",
                    "Account",
                    conflicting.pk,
                    "canonical_account_role_conflict",
                    {"code": code, "expected_slug": slug, "actual_slug": conflicting.slug},
                )
                continue
            account_class = CLASS_BY_PREFIX[code[0]]
            Account.objects.create(
                ledger_id=office.pk,
                parent_id=None,
                slug=slug,
                code=code,
                path=code,
                name=slug,
                account_class=account_class,
                normal_balance=(
                    "credit"
                    if account_class in {"liability", "equity", "revenue"}
                    else "debit"
                ),
                sort_order=sort_order,
                is_active=True,
            )

    # A positive legacy movement is safe to turn into an untouched FIFO layer
    # only when no issue exists for the same item/location. Otherwise remaining
    # quantity cannot be reconstructed without guessing.
    missing_receipts = Movement.objects.filter(quantity__gt=0, cost_layers__isnull=True)
    for move in missing_receipts.iterator():
        identity = {
            "material_id": move.material_id,
            "variant_id": move.variant_id,
            "location_kind": move.location_kind,
            "warehouse_id": move.warehouse_id,
            "branch_id": move.branch_id,
        }
        issues = Movement.objects.filter(
            material_id=move.material_id,
            variant_id=move.variant_id,
            location_kind=move.location_kind,
            warehouse_id=move.warehouse_id,
            branch_id=move.branch_id,
            quantity__lt=0,
        ).exists()
        valid_item = bool(move.material_id) != bool(move.variant_id)
        valid_location = (
            not move.variant_id
            or (
                move.location_kind == "warehouse"
                and move.warehouse_id
                and not move.branch_id
            )
            or (
                move.location_kind == "branch"
                and move.branch_id
                and not move.warehouse_id
            )
        )
        if issues or not valid_item or not valid_location:
            _queue(
                Queue,
                "inventory",
                "InventoryTransaction",
                move.pk,
                "legacy_receipt_layer_ambiguous",
                {**identity, "quantity": str(move.quantity), "unit_cost": str(move.unit_cost)},
            )
            continue
        Layer.objects.create(
            material_id=move.material_id,
            variant_id=move.variant_id,
            source_transaction_id=move.pk,
            location_kind=move.location_kind,
            warehouse_id=move.warehouse_id,
            branch_id=move.branch_id,
            unit_cost=move.unit_cost,
            original_qty=move.quantity,
            qty_remaining=move.quantity,
            metadata={"safe_backfill_0042": True},
        )

    for move in Movement.objects.filter(quantity__lt=0).iterator():
        if not Consumption.objects.filter(movement_id=move.pk).exists():
            _queue(
                Queue,
                "inventory",
                "InventoryTransaction",
                move.pk,
                "legacy_issue_missing_consumption",
                {
                    "quantity": str(move.quantity),
                    "order_line_id": move.order_line_id,
                    "reference": move.reference,
                },
            )

    # Current ProductMaterial rows can be frozen safely as a current catalog
    # baseline. They are never asserted to be the historical BOM of an old sale.
    product_ids = ProductMaterial.objects.values_list("product_id", flat=True).distinct()
    for product_id in product_ids.iterator():
        if BOMVersion.objects.filter(product_id=product_id).exists():
            continue
        rows = list(ProductMaterial.objects.filter(product_id=product_id).order_by("id"))
        if not rows:
            continue
        bom = BOMVersion.objects.create(
            product_id=product_id,
            version=1,
            status="draft",
            source_snapshot={"safe_backfill_0042": True, "scope": "current_catalog_only"},
        )
        for order, row in enumerate(rows):
            BOMLine.objects.create(
                bom_version_id=bom.pk,
                material_id=row.material_id,
                quantity=row.quantity,
                normal_spoilage_rate=row.normal_spoilage_rate,
                source_kind="legacy",
                source_reference=f"ProductMaterial:{row.pk}",
                sort_order=order,
            )
        bom.status = "published"
        bom.published_at = timezone.now()
        bom.save(update_fields=["status", "published_at"])

    planned_line_ids = Plan.objects.values_list("sale_line_id", flat=True)
    for line in SaleLine.objects.exclude(pk__in=planned_line_ids).filter(
        sale__is_deleted=False
    ).exclude(sale__order_status_ref_id="cancelled").iterator():
        if line.sale.workflow_stage_id != "pending_branch":
            _queue(
                Queue,
                "fulfillment",
                "SaleLineItem",
                line.pk,
                "legacy_sale_requires_fulfillment_reconciliation",
                {
                    "sale_id": line.sale_id,
                    "variant_id": line.variant_id,
                    "quantity": str(line.quantity),
                    "workflow_stage": line.sale.workflow_stage_id,
                },
            )

    for event in Event.objects.filter(source_reference__isnull=True).iterator():
        try:
            source_uuid = uuid.UUID(str(event.source_key))
        except (TypeError, ValueError, AttributeError):
            _queue(
                Queue,
                "accounting",
                "FinancialEvent",
                event.pk,
                "non_uuid_accounting_source",
                {
                    "source_module": event.source_module,
                    "source_type": event.source_type,
                    "source_key": event.source_key,
                },
            )
            continue
        reference, _ = SourceReference.objects.get_or_create(
            source_type=event.source_type.strip().lower(),
            source_uuid=source_uuid,
            defaults={
                "source_module": event.source_module.strip().lower(),
                "metadata": {"safe_backfill_0042": True},
            },
        )
        if reference.source_module != event.source_module.strip().lower():
            _queue(
                Queue,
                "accounting",
                "FinancialEvent",
                event.pk,
                "accounting_source_module_conflict",
                {"source_reference_id": reference.pk},
            )
            continue
        Event.objects.filter(pk=event.pk).update(source_reference_id=reference.pk)
        if event.journal_id:
            TransactionSource.objects.get_or_create(
                transaction_id=event.journal_id,
                source_reference_id=reference.pk,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0041_delivery_returns"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReconciliationQueue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(db_index=True, max_length=40)),
                ("source_type", models.CharField(max_length=80)),
                ("source_key", models.CharField(max_length=160)),
                ("reason", models.CharField(max_length=120)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("open", "باز"), ("resolved", "رفع‌شده"), ("ignored", "نادیده‌گرفته‌شده با دلیل")], db_index=True, default="open", max_length=16)),
                ("resolution_note", models.CharField(blank=True, default="", max_length=500)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_reconciliation_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "domain", "id"]},
        ),
        migrations.AddConstraint(
            model_name="reconciliationqueue",
            constraint=models.UniqueConstraint(
                fields=("domain", "source_type", "source_key", "reason"),
                name="uq_reconciliation_source_reason",
            ),
        ),
        migrations.AddIndex(
            model_name="reconciliationqueue",
            index=models.Index(
                fields=["status", "domain", "created_at"],
                name="ix_reconcile_status_domain",
            ),
        ),
        migrations.RunPython(safe_backfill, migrations.RunPython.noop),
    ]
