"""Immutable production BOMs, work in process, and finished-product lots."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .base import AppendOnlyManager, MONEY_KWARGS, QUANTITY_KWARGS


class BOMVersion(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_PUBLISHED, "منتشرشده"),
        (STATUS_RETIRED, "بازنشسته"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    product = models.ForeignKey(
        "backend.Product", on_delete=models.PROTECT, related_name="bom_versions"
    )
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    source_snapshot = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="published_bom_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product_id", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["product", "version"], name="uq_bom_product_version"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values(
                "product_id", "version", "source_snapshot", "published_at", "published_by_id"
            ).first()
            if original and self.status != self.STATUS_RETIRED:
                immutable = any(
                    original[field] != getattr(self, field)
                    for field in ("product_id", "version", "source_snapshot", "published_at", "published_by_id")
                )
                if immutable and type(self).objects.filter(
                    pk=self.pk, status=self.STATUS_PUBLISHED
                ).exists():
                    raise ValidationError("A published BOM version is immutable.")
        super().save(*args, **kwargs)


class BOMLine(models.Model):
    objects = AppendOnlyManager()
    SOURCE_PRODUCT = "product"
    SOURCE_FRAME = "frame"
    SOURCE_WORKSET = "workset"
    SOURCE_RECIPE = "recipe"
    SOURCE_LEGACY = "legacy"
    SOURCE_CHOICES = [
        (SOURCE_PRODUCT, "محصول"),
        (SOURCE_FRAME, "کلاف"),
        (SOURCE_WORKSET, "ست"),
        (SOURCE_RECIPE, "دستور کارگاه"),
        (SOURCE_LEGACY, "اسنپ‌شات قدیمی"),
    ]

    bom_version = models.ForeignKey(BOMVersion, on_delete=models.PROTECT, related_name="lines")
    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="bom_version_lines"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    normal_spoilage_rate = models.DecimalField(default=0, max_digits=6, decimal_places=2)
    source_kind = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_PRODUCT)
    source_reference = models.CharField(max_length=100, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bom_version", "material"], name="uq_bom_version_material"
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_bom_line_qty"),
            models.CheckConstraint(
                condition=models.Q(normal_spoilage_rate__gte=0, normal_spoilage_rate__lte=100),
                name="ck_bom_line_spoilage",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.bom_version.status != BOMVersion.STATUS_DRAFT:
            raise ValidationError("Published BOM lines are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.bom_version.status != BOMVersion.STATUS_DRAFT:
            raise ValidationError("Published BOM lines are immutable.")
        return super().delete(*args, **kwargs)


class ProductionRun(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_BLOCKED = "blocked"
    STATUS_RELEASED = "released"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_BLOCKED, "دارای کسری"),
        (STATUS_RELEASED, "آزادشده"),
        (STATUS_IN_PROGRESS, "در جریان"),
        (STATUS_COMPLETED, "تکمیل‌شده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    production_order = models.OneToOneField(
        "backend.ProductionOrder", on_delete=models.PROTECT, related_name="production_run"
    )
    fulfillment_plan_line = models.OneToOneField(
        "backend.FulfillmentPlanLine", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_run",
    )
    sale = models.ForeignKey(
        "backend.Sale", null=True, blank=True, on_delete=models.PROTECT, related_name="production_runs"
    )
    product = models.ForeignKey(
        "backend.Product", on_delete=models.PROTECT, related_name="production_runs"
    )
    variant = models.ForeignKey(
        "backend.ProductVariant", on_delete=models.PROTECT, related_name="production_runs"
    )
    bom_version = models.ForeignKey(
        BOMVersion, on_delete=models.PROTECT, related_name="production_runs"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    warehouse = models.ForeignKey(
        "backend.Warehouse", on_delete=models.PROTECT, related_name="production_runs"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    overhead_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    actual_material_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    total_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    released_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_production_runs",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="completed_production_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_production_run_qty"),
            models.CheckConstraint(condition=models.Q(overhead_cost__gte=0), name="ck_run_overhead"),
            models.CheckConstraint(condition=models.Q(actual_material_cost__gte=0), name="ck_run_material_cost"),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name="ck_run_total_cost"),
        ]


class MaterialRequirement(models.Model):
    run = models.ForeignKey(ProductionRun, on_delete=models.PROTECT, related_name="requirements")
    bom_line = models.ForeignKey(BOMLine, on_delete=models.PROTECT, related_name="requirements")
    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="production_requirements"
    )
    required_quantity = models.DecimalField(**QUANTITY_KWARGS)
    reservation = models.OneToOneField(
        "backend.InventoryReservation", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_requirement",
    )
    shortage_quantity = models.DecimalField(default=0, **QUANTITY_KWARGS)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["run", "material"], name="uq_run_requirement_material"),
            models.CheckConstraint(condition=models.Q(required_quantity__gt=0), name="ck_run_req_qty"),
            models.CheckConstraint(condition=models.Q(shortage_quantity__gte=0), name="ck_run_shortage"),
        ]


class ProductionEvent(models.Model):
    objects = AppendOnlyManager()
    TYPE_CONSUMPTION = "consumption"
    TYPE_EXTRA_CONSUMPTION = "extra_consumption"
    TYPE_RETURN = "return"
    TYPE_SCRAP = "scrap"
    TYPE_COMPLETION = "completion"
    TYPE_CHOICES = [
        (TYPE_CONSUMPTION, "مصرف"),
        (TYPE_EXTRA_CONSUMPTION, "مصرف اضافه"),
        (TYPE_RETURN, "برگشت"),
        (TYPE_SCRAP, "ضایعات"),
        (TYPE_COMPLETION, "تکمیل"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.CharField(max_length=160, unique=True)
    run = models.ForeignKey(ProductionRun, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    material = models.ForeignKey(
        "backend.Material", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_events",
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    total_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    reason = models.CharField(max_length=500, blank=True, default="")
    consumption = models.OneToOneField(
        "backend.InventoryConsumption", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_event",
    )
    inventory_transaction = models.OneToOneField(
        "backend.InventoryTransaction", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_event",
    )
    original_event = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )
    financial_event = models.OneToOneField(
        "backend.FinancialEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="production_event",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="authorized_production_events",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="recorded_production_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_production_event_qty"),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name="ck_production_event_cost"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values().first()
            allowed = (
                original
                and original["financial_event_id"] is None
                and self.financial_event_id is not None
                and all(
                    original[field.attname] == getattr(self, field.attname)
                    for field in self._meta.concrete_fields
                    if field.name not in {"financial_event"}
                )
            )
            if not allowed:
                raise ValueError("ProductionEvent rows are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ProductionEvent rows are immutable.")


class ProductLot(models.Model):
    objects = AppendOnlyManager()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    lot_number = models.CharField(max_length=80, unique=True)
    run = models.OneToOneField(ProductionRun, on_delete=models.PROTECT, related_name="product_lot")
    variant = models.ForeignKey(
        "backend.ProductVariant", on_delete=models.PROTECT, related_name="product_lots"
    )
    warehouse = models.ForeignKey(
        "backend.Warehouse", on_delete=models.PROTECT, related_name="product_lots"
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    unit_cost = models.DecimalField(**MONEY_KWARGS)
    total_cost = models.DecimalField(**MONEY_KWARGS)
    inventory_transaction = models.OneToOneField(
        "backend.InventoryTransaction", on_delete=models.PROTECT, related_name="product_lot"
    )
    cost_layer = models.OneToOneField(
        "backend.InventoryCostLayer", on_delete=models.PROTECT, related_name="product_lot"
    )
    completed_at = models.DateTimeField()

    class Meta:
        ordering = ["-completed_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_product_lot_qty"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_product_lot_unit_cost"),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name="ck_product_lot_total_cost"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Product lots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Product lots are immutable.")
