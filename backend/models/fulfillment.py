"""Per-sale-line fulfillment, finished-goods demand, and stock transfers."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .base import AppendOnlyManager, MONEY_KWARGS, QUANTITY_KWARGS
from .catalog import InventoryTransaction


class FulfillmentPlan(models.Model):
    STATUS_PLANNED = "planned"
    STATUS_RELEASED = "released"
    STATUS_EXECUTED = "executed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "برنامه‌ریزی‌شده"),
        (STATUS_RELEASED, "آزادشده"),
        (STATUS_EXECUTED, "اجراشده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sale_line = models.OneToOneField(
        "backend.SaleLineItem", on_delete=models.PROTECT, related_name="fulfillment_plan"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PLANNED, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_fulfillment_plans",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_fulfillment_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sale_line_id"]


class FulfillmentPlanLine(models.Model):
    ROUTE_BRANCH = "branch_stock"
    ROUTE_WAREHOUSE = "warehouse_stock"
    ROUTE_FACTORY = "factory"
    ROUTE_MERCHANT = "merchant"
    ROUTE_CHOICES = [
        (ROUTE_BRANCH, "موجودی شعبه"),
        (ROUTE_WAREHOUSE, "موجودی انبار"),
        (ROUTE_FACTORY, "تولید کارخانه"),
        (ROUTE_MERCHANT, "خرید بازرگان"),
    ]
    STATUS_PLANNED = "planned"
    STATUS_RESERVED = "reserved"
    STATUS_BLOCKED = "blocked"
    STATUS_RELEASED = "released"
    STATUS_EXECUTED = "executed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "برنامه‌ریزی‌شده"),
        (STATUS_RESERVED, "رزروشده"),
        (STATUS_BLOCKED, "دارای کسری"),
        (STATUS_RELEASED, "آزادشده"),
        (STATUS_EXECUTED, "اجراشده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    plan = models.ForeignKey(FulfillmentPlan, on_delete=models.CASCADE, related_name="lines")
    route_kind = models.CharField(max_length=24, choices=ROUTE_CHOICES, db_index=True)
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    source_location_kind = models.CharField(
        max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES, blank=True, default=""
    )
    source_warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT,
        related_name="fulfillment_plan_lines",
    )
    source_branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="fulfillment_source_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="fulfillment_plan_lines",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PLANNED, db_index=True)
    reservation = models.OneToOneField(
        "backend.InventoryReservation", null=True, blank=True, on_delete=models.PROTECT,
        related_name="fulfillment_plan_line",
    )
    production_order = models.ForeignKey(
        "backend.ProductionOrder", null=True, blank=True, on_delete=models.PROTECT,
        related_name="fulfillment_plan_lines",
    )
    bom_version = models.ForeignKey(
        "backend.BOMVersion", null=True, blank=True, on_delete=models.PROTECT,
        related_name="fulfillment_plan_lines",
    )
    shortage_request = models.ForeignKey(
        "backend.PurchaseRequest", null=True, blank=True, on_delete=models.PROTECT,
        related_name="fulfillment_plan_lines",
    )
    bom_snapshot = models.JSONField(default=list, blank=True)
    shortage_snapshot = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=500, blank=True, default="")
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan_id", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_fulfillment_line_qty"),
            models.CheckConstraint(
                condition=(
                    models.Q(route_kind="branch_stock", source_location_kind="branch", source_branch__isnull=False, source_warehouse__isnull=True)
                    | models.Q(route_kind="warehouse_stock", source_location_kind="warehouse", source_branch__isnull=True, source_warehouse__isnull=False)
                    | models.Q(route_kind__in=["factory", "merchant"], source_location_kind="", source_branch__isnull=True, source_warehouse__isnull=True)
                ),
                name="ck_fulfillment_line_source",
            ),
        ]


class MerchantSupplyDemand(models.Model):
    STATUS_OPEN = "open"
    STATUS_ORDERED = "ordered"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "باز"),
        (STATUS_ORDERED, "سفارش‌شده"),
        (STATUS_RECEIVED, "تحویل‌شده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    plan_line = models.OneToOneField(
        FulfillmentPlanLine, on_delete=models.PROTECT, related_name="merchant_demand"
    )
    product = models.ForeignKey(
        "backend.Product", null=True, blank=True, on_delete=models.PROTECT,
        related_name="merchant_supply_demands",
    )
    variant = models.ForeignKey(
        "backend.ProductVariant", null=True, blank=True, on_delete=models.PROTECT,
        related_name="merchant_supply_demands",
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    destination_kind = models.CharField(max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES)
    warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT,
        related_name="merchant_supply_demands",
    )
    branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="merchant_demand_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="merchant_supply_demands",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    receipt_movement = models.OneToOneField(
        InventoryTransaction, null=True, blank=True, on_delete=models.PROTECT,
        related_name="merchant_supply_demand",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="merchant_supply_demands",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_merchant_demand_qty"),
            models.CheckConstraint(
                condition=(
                    models.Q(destination_kind="warehouse", warehouse__isnull=False, branch__isnull=True)
                    | models.Q(destination_kind="branch", warehouse__isnull=True, branch__isnull=False)
                ),
                name="ck_merchant_demand_location",
            ),
        ]


class StockTransfer(models.Model):
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_IN_TRANSIT, "در مسیر"),
        (STATUS_COMPLETED, "تکمیل‌شده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.CharField(max_length=120, unique=True)
    plan_line = models.ForeignKey(
        FulfillmentPlanLine, null=True, blank=True, on_delete=models.PROTECT,
        related_name="stock_transfers",
    )
    variant = models.ForeignKey(
        "backend.ProductVariant", on_delete=models.PROTECT, related_name="stock_transfers"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    source_kind = models.CharField(max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES)
    source_warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    source_branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="stock_transfer_source_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    destination_kind = models.CharField(max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES)
    destination_warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    destination_branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="stock_transfer_destination_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_IN_TRANSIT, db_index=True)
    issue_movement = models.OneToOneField(
        InventoryTransaction, null=True, blank=True, on_delete=models.PROTECT, related_name="transfer_issue"
    )
    receipt_movement = models.OneToOneField(
        InventoryTransaction, null=True, blank=True, on_delete=models.PROTECT, related_name="transfer_receipt"
    )
    accounting_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="stock_transfer",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_stock_transfer_qty"),
        ]


class DeliveryDocument(models.Model):
    """Immutable, all-or-nothing physical delivery of one sale."""
    objects = AppendOnlyManager()

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CHOICES = [(STATUS_DRAFT, "پیش‌نویس"), (STATUS_POSTED, "ثبت‌شده")]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.CharField(max_length=160, unique=True)
    sale = models.OneToOneField(
        "backend.Sale", on_delete=models.PROTECT, related_name="delivery_document"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    total_actual_cogs = models.DecimalField(default=0, **MONEY_KWARGS)
    sale_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="sale_delivery",
    )
    cogs_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="cogs_delivery",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posted_deliveries",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_actual_cogs__gte=0), name="ck_delivery_cogs"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values(
                "status", "total_actual_cogs", "sale_event_id", "cogs_event_id",
                "posted_by_id", "posted_at",
            ).first()
            allowed = old and old["status"] == self.STATUS_DRAFT and self.status == self.STATUS_POSTED
            if not allowed:
                raise ValidationError("Posted delivery documents are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery documents are immutable; use a return document.")


class DeliveryLine(models.Model):
    objects = AppendOnlyManager()
    delivery = models.ForeignKey(
        DeliveryDocument, on_delete=models.PROTECT, related_name="lines"
    )
    sale_line = models.ForeignKey(
        "backend.SaleLineItem", on_delete=models.PROTECT, related_name="delivery_lines"
    )
    fulfillment_plan_line = models.OneToOneField(
        FulfillmentPlanLine, on_delete=models.PROTECT, related_name="delivery_line"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    total_actual_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    consumption = models.OneToOneField(
        "backend.InventoryConsumption", on_delete=models.PROTECT, related_name="delivery_line"
    )
    product_lot = models.ForeignKey(
        "backend.ProductLot", null=True, blank=True, on_delete=models.PROTECT,
        related_name="delivery_lines",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_line_id", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_delivery_line_qty"),
            models.CheckConstraint(
                condition=models.Q(total_actual_cost__gte=0), name="ck_delivery_line_cost"
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Delivery lines are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery lines are immutable.")


class SalesReturn(models.Model):
    objects = AppendOnlyManager()
    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CHOICES = [(STATUS_DRAFT, "پیش‌نویس"), (STATUS_POSTED, "ثبت‌شده")]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.CharField(max_length=160, unique=True)
    delivery = models.ForeignKey(
        DeliveryDocument, on_delete=models.PROTECT, related_name="returns"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    revenue_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    vat_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    total_actual_cogs = models.DecimalField(default=0, **MONEY_KWARGS)
    revenue_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="sales_return_revenue",
    )
    cogs_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="sales_return_cogs",
    )
    reason = models.CharField(max_length=500)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posted_sales_returns",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(revenue_amount__gte=0), name="ck_return_revenue"),
            models.CheckConstraint(condition=models.Q(vat_amount__gte=0), name="ck_return_vat"),
            models.CheckConstraint(condition=models.Q(total_actual_cogs__gte=0), name="ck_return_cogs"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values("status").first()
            if not (old and old["status"] == self.STATUS_DRAFT and self.status == self.STATUS_POSTED):
                raise ValidationError("Posted sales returns are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sales returns are immutable; issue a linked correction.")


class SalesReturnLine(models.Model):
    objects = AppendOnlyManager()
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.PROTECT, related_name="lines")
    delivery_line = models.ForeignKey(
        DeliveryLine, on_delete=models.PROTECT, related_name="return_lines"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    revenue_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    vat_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    actual_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    allocation_snapshot = models.JSONField(default=list, blank=True)
    inventory_transaction = models.OneToOneField(
        "backend.InventoryTransaction", on_delete=models.PROTECT,
        related_name="sales_return_line",
    )
    return_cost_layer = models.OneToOneField(
        "backend.InventoryCostLayer", on_delete=models.PROTECT,
        related_name="sales_return_line",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sales_return", "delivery_line"], name="uq_return_delivery_line"
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_return_line_qty"),
            models.CheckConstraint(condition=models.Q(actual_cost__gte=0), name="ck_return_line_cost"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Sales return lines are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sales return lines are immutable.")
