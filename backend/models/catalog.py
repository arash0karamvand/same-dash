"""Product catalog, materials, and append-only inventory movements."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from backend.soft_delete import SoftDeleteModel
from .base import AppendOnlyModel, MONEY_KWARGS, QUANTITY_KWARGS, ReferenceCodeModel
from .config import Branch, MaterialStatus


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
    frame = models.ForeignKey(
        "backend.Frame",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="linked_products",
    )
    furniture_workset = models.ForeignKey(
        "backend.FurnitureWorkset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    suite_config = models.JSONField(default=list, blank=True)
    paint_recipe = models.ForeignKey(
        "backend.WorkshopRecipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_paint",
    )
    fabric_recipe = models.ForeignKey(
        "backend.WorkshopRecipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_fabric",
    )
    foam_recipe = models.ForeignKey(
        "backend.WorkshopRecipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_foam",
    )
    cushion_recipe = models.ForeignKey(
        "backend.WorkshopRecipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_cushion",
    )
    webbing_recipe = models.ForeignKey(
        "backend.WorkshopRecipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_webbing",
    )
    BUILD_MODEL_FRAME_LINE = "frame_line"
    BUILD_MODEL_CHOICES = [
        (BUILD_MODEL_FRAME_LINE, "خط کلاف"),
    ]
    PIPELINE_END_UPHOLSTERY = "upholstery"
    PIPELINE_END_ASSEMBLY = "assembly"
    PIPELINE_END_CHOICES = [
        (PIPELINE_END_UPHOLSTERY, "رویه‌کوبی"),
        (PIPELINE_END_ASSEMBLY, "مونتاژ"),
    ]
    build_model = models.CharField(
        max_length=20,
        choices=BUILD_MODEL_CHOICES,
        default=BUILD_MODEL_FRAME_LINE,
        db_index=True,
    )
    needs_paint = models.BooleanField(default=True)
    pipeline_end = models.CharField(
        max_length=20,
        choices=PIPELINE_END_CHOICES,
        default=PIPELINE_END_UPHOLSTERY,
    )
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
    target_margin_percent = models.DecimalField(
        null=True, blank=True, max_digits=6, decimal_places=2
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(default_price__gte=0), name="ck_product_price"),
            models.CheckConstraint(
                condition=models.Q(target_margin_percent__isnull=True)
                | models.Q(target_margin_percent__gte=0, target_margin_percent__lte=100),
                name="ck_product_target_margin",
            ),
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

    def stock_at(self, *, location_kind=None, warehouse_id=None, branch_id=None):
        qs = self.inventory_movements.all()
        if location_kind:
            qs = qs.filter(location_kind=location_kind)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs.aggregate(total=Sum("quantity"))["total"] or Decimal("0")

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
    USAGE_WOOD = "wood"
    USAGE_PAINT = "paint"
    USAGE_FABRIC = "fabric"
    USAGE_FOAM = "foam"
    USAGE_CUSHION = "cushion"
    USAGE_WEBBING = "webbing"
    USAGE_OTHER = "other"
    USAGE_KIND_CHOICES = [
        (USAGE_WOOD, "چوب"),
        (USAGE_PAINT, "رنگ"),
        (USAGE_FABRIC, "پارچه"),
        (USAGE_FOAM, "اسفنج"),
        (USAGE_CUSHION, "کوسن"),
        (USAGE_WEBBING, "تسمه"),
        (USAGE_OTHER, "سایر"),
    ]

    name = models.CharField(max_length=150)
    usage_kind = models.CharField(
        "نوع مصرف کارخانه",
        max_length=20,
        choices=USAGE_KIND_CHOICES,
        default=USAGE_OTHER,
        db_index=True,
    )
    color_name = models.CharField(max_length=50, blank=True)
    color_hex = models.CharField(max_length=7, default="#cccccc")
    sku = models.CharField(max_length=50, blank=True, db_index=True)
    unit = models.CharField(max_length=20, default="متر")
    unit_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    VALUATION_WEIGHTED = "weighted_average"
    VALUATION_FIFO = "fifo"
    VALUATION_CHOICES = [
        (VALUATION_WEIGHTED, "میانگین موزون"),
        (VALUATION_FIFO, "FIFO"),
    ]
    valuation_method = models.CharField(
        max_length=20, choices=VALUATION_CHOICES, default=VALUATION_WEIGHTED
    )
    reorder_point = models.DecimalField(default=0, **QUANTITY_KWARGS)
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
            models.CheckConstraint(condition=models.Q(reorder_point__gte=0), name="ck_material_reorder"),
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
    normal_spoilage_rate = models.DecimalField(default=0, max_digits=6, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "product_id", "material_id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_bom_quantity"),
            models.CheckConstraint(
                condition=models.Q(normal_spoilage_rate__gte=0, normal_spoilage_rate__lte=100),
                name="ck_bom_spoilage",
            ),
        ]


class InventoryTransaction(AppendOnlyModel):
    LOCATION_WAREHOUSE = "warehouse"
    LOCATION_BRANCH = "branch"
    LOCATION_KIND_CHOICES = [
        (LOCATION_WAREHOUSE, "انبار"),
        (LOCATION_BRANCH, "شعبه"),
    ]

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
    location_kind = models.CharField(
        max_length=16, choices=LOCATION_KIND_CHOICES, blank=True, default=""
    )
    warehouse = models.ForeignKey(
        "backend.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="stock_branch",
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
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

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
            models.CheckConstraint(
                condition=(
                    models.Q(variant__isnull=True)
                    | (
                        models.Q(
                            location_kind="warehouse",
                            warehouse__isnull=False,
                            branch__isnull=True,
                        )
                        | models.Q(
                            location_kind="branch",
                            warehouse__isnull=True,
                            branch__isnull=False,
                        )
                    )
                ),
                name="ck_inventory_variant_location",
            ),
        ]
        indexes = [
            models.Index(fields=["material", "created_at"], name="ix_inventory_material"),
            models.Index(fields=["variant", "created_at"], name="ix_inventory_variant"),
            models.Index(fields=["variant", "location_kind", "warehouse"], name="ix_inventory_loc_wh"),
            models.Index(fields=["variant", "location_kind", "branch"], name="ix_inventory_loc_br"),
        ]


class MaterialStocktake(models.Model):
    """برگه انبارگردانی متریال — شمارش فیزیکی در برابر موجودی سیستمی."""

    TYPE_CYCLE = "cycle"
    TYPE_ANNUAL = "annual"
    TYPE_SPOT = "spot"
    TYPE_CHOICES = [
        (TYPE_CYCLE, "دوره‌ای"),
        (TYPE_ANNUAL, "پایان سال"),
        (TYPE_SPOT, "موردی"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_CLOSED, "بسته شده"),
    ]

    count_type = models.CharField("نوع شمارش", max_length=20, choices=TYPE_CHOICES, default=TYPE_CYCLE)
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    scope_note = models.CharField("محدوده", max_length=200, blank=True, default="")
    supervisor_name = models.CharField("سرپرست", max_length=120, blank=True, default="")
    counter_names = models.CharField("شمارش‌گرها", max_length=240, blank=True, default="")
    observer_name = models.CharField("ناظر", max_length=120, blank=True, default="")
    started_at = models.DateTimeField("شروع")
    finished_at = models.DateTimeField("پایان", null=True, blank=True)
    journal = models.ForeignKey(
        "backend.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="material_stocktakes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="material_stocktakes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        verbose_name = "برگه انبارگردانی"
        verbose_name_plural = "برگه‌های انبارگردانی"

    def __str__(self):
        return f"{self.get_count_type_display()} — {self.started_at:%Y-%m-%d}"


class MaterialStocktakeLine(models.Model):
    CONDITION_SOUND = "sound"
    CONDITION_DAMAGED = "damaged"
    CONDITION_EXPIRED = "expired"
    CONDITION_CONSIGNMENT = "consignment"
    CONDITION_CHOICES = [
        (CONDITION_SOUND, "سالم"),
        (CONDITION_DAMAGED, "آسیب‌دیده"),
        (CONDITION_EXPIRED, "تاریخ‌گذشته"),
        (CONDITION_CONSIGNMENT, "امانی"),
    ]
    CAUSE_ENTRY = "entry_error"
    CAUSE_MISPLACE = "misplacement"
    CAUSE_SHRINK = "shrinkage"
    CAUSE_WASTE = "unrecorded_waste"
    CAUSE_SYNC = "sync_delay"
    CAUSE_CHOICES = [
        (CAUSE_ENTRY, "خطای ثبت"),
        (CAUSE_MISPLACE, "جانمایی اشتباه"),
        (CAUSE_SHRINK, "مفقودی"),
        (CAUSE_WASTE, "ضایعات ثبت‌نشده"),
        (CAUSE_SYNC, "تاخیر هماهنگی سیستم"),
    ]

    stocktake = models.ForeignKey(
        MaterialStocktake,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="stocktake_lines",
    )
    system_qty = models.DecimalField("موجودی سیستمی", **QUANTITY_KWARGS)
    physical_qty = models.DecimalField("موجودی فیزیکی", **QUANTITY_KWARGS)
    unit_cost = models.DecimalField("قیمت واحد", **MONEY_KWARGS, default=0)
    condition = models.CharField(
        "وضعیت کیفی",
        max_length=20,
        choices=CONDITION_CHOICES,
        default=CONDITION_SOUND,
    )
    root_cause = models.CharField("علت مغایرت", max_length=32, blank=True, default="")

    class Meta:
        ordering = ["material_id"]
        verbose_name = "ردیف انبارگردانی"
        verbose_name_plural = "ردیف‌های انبارگردانی"
        constraints = [
            models.UniqueConstraint(fields=["stocktake", "material"], name="uq_stocktake_material"),
            models.CheckConstraint(condition=models.Q(physical_qty__gte=0), name="ck_stocktake_physical"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_stocktake_line_cost"),
        ]


class InventoryCostLayer(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="cost_layers")
    source_transaction = models.ForeignKey(
        InventoryTransaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cost_layers",
    )
    unit_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    qty_remaining = models.DecimalField(default=0, **QUANTITY_KWARGS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="ck_cost_layer_unit"),
            models.CheckConstraint(condition=models.Q(qty_remaining__gte=0), name="ck_cost_layer_qty"),
        ]
