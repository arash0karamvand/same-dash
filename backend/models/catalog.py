"""Product catalog, materials, and append-only inventory movements."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from backend.soft_delete import SoftDeleteModel
from .base import AppendOnlyModel, MONEY_KWARGS, QUANTITY_KWARGS, ReferenceCodeModel
from .config import MaterialStatus


class ProductCategory(SoftDeleteModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#6366f1")
    icon = models.CharField(max_length=8, blank=True, default="📦")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Product(SoftDeleteModel):
    category = models.ForeignKey(
        ProductCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="products"
    )
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, blank=True, db_index=True)
    brand = models.CharField(max_length=100, blank=True)
    product_model = models.CharField(max_length=100, blank=True)
    fabric = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, default="عدد")
    attributes = models.JSONField(default=dict, blank=True)
    default_price = models.DecimalField(default=0, **MONEY_KWARGS)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(default_price__gte=0), name="ck_product_price"),
        ]

    @property
    def display_price(self):
        return Decimal(self.default_price or 0)

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    color_name = models.CharField(max_length=50)
    color_hex = models.CharField(max_length=7, default="#cccccc")
    sku = models.CharField(max_length=60, blank=True)
    price = models.DecimalField(default=0, **MONEY_KWARGS)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "color_name"], name="uq_variant_color"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="ck_variant_price"),
        ]

    @property
    def stock(self):
        return self.inventory_movements.aggregate(total=Sum("quantity"))["total"] or Decimal("0")

    def __str__(self):
        return f"{self.product.name} — {self.color_name}"


class Material(ReferenceCodeModel, SoftDeleteModel):
    reference_code_fields = {"approval_status": "approval_status_ref"}
    APPROVAL_PENDING = "pending"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "در انتظار تایید اداری"),
        (APPROVAL_APPROVED, "تایید شده"),
        (APPROVAL_REJECTED, "رد شده"),
    ]
    name = models.CharField(max_length=150)
    color_name = models.CharField(max_length=50, blank=True)
    color_hex = models.CharField(max_length=7, default="#cccccc")
    sku = models.CharField(max_length=50, blank=True, db_index=True)
    unit = models.CharField(max_length=20, default="متر")
    unit_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    approval_status_ref = models.ForeignKey(
        MaterialStatus,
        db_column="approval_status",
        default=APPROVAL_APPROVED,
        on_delete=models.PROTECT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_materials",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_materials",
    )
    rejection_reason = models.TextField(blank=True)
    inventory_accounted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_material_cost"),
        ]

    @property
    def stock(self):
        return self.inventory_movements.aggregate(total=Sum("quantity"))["total"] or Decimal("0")

    def __str__(self):
        return f"{self.name} ({self.color_name})" if self.color_name else self.name

    approval_status = property(
        lambda self: self.reference_code("approval_status"),
        lambda self, value: self.set_reference_code("approval_status", value),
    )

    def get_approval_status_display(self):
        return self.reference_label("approval_status")


class ProductMaterial(models.Model):
    pk = models.CompositePrimaryKey("product", "material")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_materials")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="product_links")
    quantity = models.DecimalField(default=1, **QUANTITY_KWARGS)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "product_id", "material_id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_bom_quantity"),
        ]


class InventoryTransaction(AppendOnlyModel):
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_movements"
    )
    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    order_line = models.ForeignKey(
        "backend.SaleLineItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    unit_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    reason = models.CharField(max_length=80)
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(material__isnull=False, variant__isnull=True)
                    | models.Q(material__isnull=True, variant__isnull=False)
                ),
                name="ck_inventory_one_item",
            ),
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="ck_inventory_quantity_nonzero"
            ),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_inventory_cost"),
        ]
        indexes = [
            models.Index(fields=["material", "created_at"], name="ix_inventory_material"),
            models.Index(fields=["variant", "created_at"], name="ix_inventory_variant"),
        ]
