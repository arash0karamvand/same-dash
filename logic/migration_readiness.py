"""Repeatable readiness scan for the phase 1-6 data migration."""

from django.db import transaction

from backend.models import (
    FinancialEvent,
    InventoryConsumption,
    InventoryCostLayer,
    InventoryTransaction,
    ReconciliationQueue,
)
from logic.feature_flags import rollout_status


def _item_filter(move):
    return {
        "material_id": move.material_id,
        "variant_id": move.variant_id,
        "location_kind": move.location_kind,
        "warehouse_id": move.warehouse_id,
        "branch_id": move.branch_id,
    }


def readiness_report():
    missing_receipts = InventoryTransaction.objects.filter(
        quantity__gt=0, cost_layers__isnull=True
    ).distinct()
    legacy_issues = InventoryTransaction.objects.filter(
        quantity__lt=0, consumption__isnull=True
    )
    non_uuid_events = 0
    from uuid import UUID

    for key in FinancialEvent.objects.filter(
        source_reference__isnull=True
    ).values_list("source_key", flat=True).iterator():
        try:
            UUID(str(key))
        except (TypeError, ValueError, AttributeError):
            non_uuid_events += 1
    return {
        "flags": rollout_status(),
        "missing_receipt_layers": missing_receipts.count(),
        "legacy_issues_without_consumption": legacy_issues.count(),
        "financial_events_without_source_reference": FinancialEvent.objects.filter(
            source_reference__isnull=True
        ).count(),
        "non_uuid_financial_event_sources": non_uuid_events,
        "open_reconciliation_items": ReconciliationQueue.objects.filter(
            status=ReconciliationQueue.STATUS_OPEN
        ).count(),
    }


@transaction.atomic
def apply_safe_backfill():
    created_layers = queued = 0
    for move in InventoryTransaction.objects.select_for_update().filter(
        quantity__gt=0, cost_layers__isnull=True
    ).distinct():
        identity = _item_filter(move)
        has_issue = InventoryTransaction.objects.filter(
            **identity, quantity__lt=0
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
        if has_issue or not valid_item or not valid_location:
            _, created = ReconciliationQueue.objects.get_or_create(
                domain="inventory",
                source_type="InventoryTransaction",
                source_key=str(move.pk),
                reason="legacy_receipt_layer_ambiguous",
                defaults={
                    "details": {
                        **identity,
                        "quantity": str(move.quantity),
                        "unit_cost": str(move.unit_cost),
                    }
                },
            )
            queued += int(created)
            continue
        InventoryCostLayer.objects.create(
            **identity,
            source_transaction=move,
            unit_cost=move.unit_cost,
            original_qty=move.quantity,
            qty_remaining=move.quantity,
            metadata={"safe_backfill_command": True},
        )
        created_layers += 1
    for move in InventoryTransaction.objects.filter(
        quantity__lt=0, consumption__isnull=True
    ):
        _, created = ReconciliationQueue.objects.get_or_create(
            domain="inventory",
            source_type="InventoryTransaction",
            source_key=str(move.pk),
            reason="legacy_issue_missing_consumption",
            defaults={
                "details": {
                    "quantity": str(move.quantity),
                    "order_line_id": move.order_line_id,
                    "reference": move.reference,
                }
            },
        )
        queued += int(created)
    return {"created_layers": created_layers, "queued": queued, **readiness_report()}
