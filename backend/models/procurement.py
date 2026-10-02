"""Unified procurement requests, orders, receipts, and explicit variances."""

import uuid

from django.conf import settings
from django.db import models

from .base import MONEY_KWARGS, QUANTITY_KWARGS
from .catalog import InventoryTransaction


class PurchaseRequest(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_ORDERED = "ordered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_APPROVED, "تاییدشده"),
        (STATUS_ORDERED, "سفارش‌گذاری‌شده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    destination_kind = models.CharField(max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES)
    warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="purchase_request_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_requests",
    )
    note = models.CharField(max_length=500, blank=True, default="")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="approved_purchase_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(destination_kind=InventoryTransaction.LOCATION_WAREHOUSE, warehouse__isnull=False, branch__isnull=True)
                    | models.Q(destination_kind=InventoryTransaction.LOCATION_BRANCH, warehouse__isnull=True, branch__isnull=False)
                ),
                name="ck_purchase_request_location",
            ),
        ]


class PurchaseRequestLine(models.Model):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="purchase_request_lines"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    source_type = models.CharField(max_length=40)
    source_key = models.CharField(max_length=120)
    sale = models.ForeignKey(
        "backend.Sale", null=True, blank=True, on_delete=models.PROTECT,
        related_name="purchase_request_lines",
    )
    order_line = models.ForeignKey(
        "backend.SaleLineItem", null=True, blank=True, on_delete=models.PROTECT,
        related_name="purchase_request_lines",
    )
    production_order = models.ForeignKey(
        "backend.ProductionOrder", null=True, blank=True, on_delete=models.PROTECT,
        related_name="purchase_request_lines",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_key", "material"],
                name="uq_shortage_source_material",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_purchase_request_line_qty"),
        ]


class PurchaseOrder(models.Model):
    STATUS_APPROVED = "approved"
    STATUS_PARTIAL = "partial"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_APPROVED, "تاییدشده"),
        (STATUS_PARTIAL, "تحویل ناقص"),
        (STATUS_RECEIVED, "تحویل کامل"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request = models.OneToOneField(
        PurchaseRequest, on_delete=models.PROTECT, related_name="purchase_order"
    )
    supplier = models.ForeignKey(
        "backend.MaterialSupplier", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_APPROVED, db_index=True)
    expected_at = models.DateField(null=True, blank=True)
    destination_kind = models.CharField(max_length=16, choices=InventoryTransaction.LOCATION_KIND_CHOICES)
    warehouse = models.ForeignKey(
        "backend.Warehouse", null=True, blank=True, on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    branch = models.ForeignKey(
        "backend.Branch", to_field="code", db_column="purchase_order_branch",
        null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_orders",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="approved_purchase_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(destination_kind=InventoryTransaction.LOCATION_WAREHOUSE, warehouse__isnull=False, branch__isnull=True)
                    | models.Q(destination_kind=InventoryTransaction.LOCATION_BRANCH, warehouse__isnull=True, branch__isnull=False)
                ),
                name="ck_purchase_order_location",
            ),
        ]


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    request_line = models.OneToOneField(
        PurchaseRequestLine, on_delete=models.PROTECT, related_name="purchase_order_line"
    )
    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="purchase_order_lines"
    )
    ordered_quantity = models.DecimalField(**QUANTITY_KWARGS)
    received_quantity = models.DecimalField(default=0, **QUANTITY_KWARGS)
    unit_price = models.DecimalField(default=0, **MONEY_KWARGS)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(ordered_quantity__gt=0), name="ck_purchase_order_line_qty"),
            models.CheckConstraint(condition=models.Q(received_quantity__gte=0), name="ck_purchase_order_received_qty"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_purchase_order_price"),
            models.CheckConstraint(
                condition=models.Q(received_quantity__lte=models.F("ordered_quantity")),
                name="ck_purchase_order_remaining",
            ),
        ]


class GoodsReceipt(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [(STATUS_DRAFT, "پیش‌نویس"), (STATUS_APPROVED, "تاییدشده")]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    receipt_number = models.CharField(max_length=80)
    invoice_number = models.CharField(max_length=80)
    is_final = models.BooleanField(default=False)
    purchase_invoice = models.OneToOneField(
        "backend.PurchaseInvoice", null=True, blank=True, on_delete=models.PROTECT,
        related_name="goods_receipt",
    )
    accounting_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="goods_receipt",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="approved_goods_receipts",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="goods_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "receipt_number"], name="uq_order_receipt_number"),
            models.UniqueConstraint(
                fields=["order", "invoice_number"], name="uq_order_invoice_number"
            ),
        ]


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="goods_receipt_lines"
    )
    expected_quantity = models.DecimalField(**QUANTITY_KWARGS)
    received_quantity = models.DecimalField(**QUANTITY_KWARGS)
    ordered_unit_price = models.DecimalField(default=0, **MONEY_KWARGS)
    received_unit_price = models.DecimalField(default=0, **MONEY_KWARGS)
    inventory_move = models.OneToOneField(
        "backend.InventoryTransaction", null=True, blank=True, on_delete=models.PROTECT,
        related_name="goods_receipt_line",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["receipt", "order_line"], name="uq_receipt_order_line"),
            models.CheckConstraint(condition=models.Q(expected_quantity__gt=0), name="ck_receipt_expected_qty"),
            models.CheckConstraint(condition=models.Q(received_quantity__gt=0), name="ck_receipt_received_qty"),
            models.CheckConstraint(condition=models.Q(received_unit_price__gte=0), name="ck_receipt_price"),
        ]


class ProcurementAdjustment(models.Model):
    KIND_QUANTITY = "quantity"
    KIND_PRICE = "price"
    KIND_CHOICES = [(KIND_QUANTITY, "مقدار"), (KIND_PRICE, "قیمت")]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    receipt_line = models.ForeignKey(
        GoodsReceiptLine, on_delete=models.PROTECT, related_name="adjustments"
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    expected_value = models.DecimalField(max_digits=18, decimal_places=3)
    actual_value = models.DecimalField(max_digits=18, decimal_places=3)
    reason = models.CharField(max_length=500)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="procurement_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
