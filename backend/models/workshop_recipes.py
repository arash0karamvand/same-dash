"""دستورهای دست‌کار کارخانه — رنگ، پارچه، فوم، کوسن."""

from django.db import models

from backend.soft_delete import SoftDeleteModel
from .base import MONEY_KWARGS, QUANTITY_KWARGS


class WorkshopRecipe(SoftDeleteModel):
    KIND_PAINT = "paint"
    KIND_FABRIC = "fabric"
    KIND_FOAM = "foam"
    KIND_CUSHION = "cushion"
    KIND_WEBBING = "webbing"
    KIND_CHOICES = [
        (KIND_PAINT, "رنگ"),
        (KIND_FABRIC, "پارچه"),
        (KIND_FOAM, "اسفنج"),
        (KIND_CUSHION, "کوسن"),
        (KIND_WEBBING, "تسمه"),
    ]
    PAINT_CATEGORY_THINNER = "thinner"
    PAINT_CATEGORY_PAINT = "paint"
    PAINT_CATEGORY_PUTTY = "putty"
    PAINT_CATEGORY_PATINA = "patina"
    PAINT_CATEGORY_ABRASIVE = "abrasive"
    PAINT_CATEGORY_CHEMICAL = "chemical"
    PAINT_CATEGORY_CHOICES = [
        (PAINT_CATEGORY_THINNER, "تینر"),
        (PAINT_CATEGORY_PAINT, "رنگ و پلی‌استر"),
        (PAINT_CATEGORY_PUTTY, "بتونه و سیلر"),
        (PAINT_CATEGORY_PATINA, "پتینه و ورق طلا"),
        (PAINT_CATEGORY_ABRASIVE, "سنباده و ابزار مصرفی"),
        (PAINT_CATEGORY_CHEMICAL, "هاردنر و شیمیایی"),
    ]
    PAINT_UNITS = ("لیتر", "کیلوگرم", "ورق", "قوطی", "گالن", "حلب")
    FABRIC_CATEGORY_VELVET_PLAIN = "velvet_plain"
    FABRIC_CATEGORY_VELVET_PATTERN = "velvet_pattern"
    FABRIC_CATEGORY_WASHED_COTTON = "washed_cotton"
    FABRIC_CATEGORY_HEAVY_LINEN = "heavy_linen"
    FABRIC_CATEGORY_MATTE_LEATHER = "matte_leather"
    FABRIC_CATEGORY_SOFT_SUEDE = "soft_suede"
    FABRIC_CATEGORY_LOOP_WEAVE = "loop_weave"
    FABRIC_CATEGORY_STRETCH = "stretch_cloth"
    FABRIC_CATEGORY_MATTE_SATIN = "matte_satin"
    FABRIC_CATEGORY_OUTDOOR = "outdoor_cloth"
    FABRIC_CATEGORY_CHOICES = [
        (FABRIC_CATEGORY_VELVET_PLAIN, "مخمل ساده"),
        (FABRIC_CATEGORY_VELVET_PATTERN, "مخمل طرح‌دار"),
        (FABRIC_CATEGORY_WASHED_COTTON, "کتان شست"),
        (FABRIC_CATEGORY_HEAVY_LINEN, "لینن ضخیم"),
        (FABRIC_CATEGORY_MATTE_LEATHER, "چرم مصنوعی مات"),
        (FABRIC_CATEGORY_SOFT_SUEDE, "جیر نرم"),
        (FABRIC_CATEGORY_LOOP_WEAVE, "بافت حلقه‌ای"),
        (FABRIC_CATEGORY_STRETCH, "پارچه کشسان"),
        (FABRIC_CATEGORY_MATTE_SATIN, "ساتن مات"),
        (FABRIC_CATEGORY_OUTDOOR, "پارچه فضای باز"),
    ]
    FABRIC_COMPANY_NURA = "nura_weave"
    FABRIC_COMPANY_ARIA = "aria_textile"
    FABRIC_COMPANY_SEPEHR = "sepehr_hide"
    FABRIC_COMPANY_ROSHAN = "roshan_line"
    FABRIC_COMPANY_CHOICES = [
        (FABRIC_COMPANY_NURA, "بافندگی نورا"),
        (FABRIC_COMPANY_ARIA, "منسوجات آریا"),
        (FABRIC_COMPANY_SEPEHR, "چرمینه سپهر"),
        (FABRIC_COMPANY_ROSHAN, "کالکشن روشان"),
    ]
    FABRIC_COUNTRIES = ("ایران", "ترکیه", "چین", "ایتالیا", "هند", "اسپانیا")
    FABRIC_STOCK_UNIT = "متر"

    kind = models.CharField("نوع دستور", max_length=20, choices=KIND_CHOICES, db_index=True)
    name = models.CharField("نام", max_length=150)
    color_name = models.CharField("رنگ / فام", max_length=80, blank=True, default="")
    note = models.TextField("توضیحات", blank=True, default="")
    item_code = models.CharField("کد رهگیری", max_length=40, blank=True, null=True, unique=True)
    paint_category = models.CharField(
        "دسته‌بندی رنگ",
        max_length=20,
        blank=True,
        default="",
        choices=PAINT_CATEGORY_CHOICES,
    )
    brand = models.CharField("برند", max_length=120, blank=True, default="")
    stock_unit = models.CharField("واحد شمارش", max_length=20, blank=True, default="")
    current_stock = models.DecimalField("موجودی", **QUANTITY_KWARGS, default=0)
    min_stock = models.DecimalField("نقطه سفارش", **QUANTITY_KWARGS, default=0)
    storage_shelf = models.CharField("موقعیت قفسه", max_length=80, blank=True, default="")
    unit_cost = models.DecimalField("نرخ واحد", **MONEY_KWARGS, default=0)
    technical_specs = models.TextField("مشخصات فنی", blank=True, default="")
    fabric_category = models.CharField(
        "دسته‌بندی پارچه",
        max_length=40,
        blank=True,
        default="",
        choices=FABRIC_CATEGORY_CHOICES,
    )
    company_code = models.CharField(
        "شرکت پارچه",
        max_length=40,
        blank=True,
        default="",
        choices=FABRIC_COMPANY_CHOICES,
    )
    origin_country = models.CharField("کشور سازنده", max_length=40, blank=True, default="")
    roll_count = models.PositiveIntegerField("تعداد طاقه", default=1)
    image_url = models.TextField("تصویر کالیته", blank=True, default="")
    gallery_urls = models.JSONField("گالری تصاویر", blank=True, default=list)
    fabric_country = models.ForeignKey(
        "backend.FabricCatalogNode",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="country_recipes",
    )
    fabric_brand = models.ForeignKey(
        "backend.FabricCatalogNode",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="brand_recipes",
    )
    fabric_color = models.ForeignKey(
        "backend.FabricCatalogNode",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="color_recipes",
    )
    fabric_type = models.ForeignKey(
        "backend.FabricCatalogNode",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="type_recipes",
    )
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = "دستور دست‌کار"
        verbose_name_plural = "دستورهای دست‌کار"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_stock__gte=0),
                name="ck_workshop_recipe_stock",
            ),
            models.CheckConstraint(
                condition=models.Q(min_stock__gte=0),
                name="ck_workshop_recipe_min_stock",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="ck_workshop_recipe_unit_cost",
            ),
            models.CheckConstraint(
                condition=models.Q(roll_count__gte=0),
                name="ck_workshop_recipe_roll_count",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.name}"


class WorkshopRecipeMaterial(models.Model):
    recipe = models.ForeignKey(
        WorkshopRecipe,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    material = models.ForeignKey(
        "backend.Material",
        on_delete=models.PROTECT,
        related_name="workshop_recipe_links",
    )
    quantity = models.DecimalField("مقدار", **QUANTITY_KWARGS, default=1)
    normal_spoilage_rate = models.DecimalField("نرخ ضایعات عادی", default=0, max_digits=6, decimal_places=2)
    unit = models.CharField("واحد", max_length=20, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "متریال دستور دست‌کار"
        verbose_name_plural = "متریال‌های دستور دست‌کار"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "material"], name="uq_workshop_recipe_material"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_workshop_recipe_qty"),
            models.CheckConstraint(
                condition=models.Q(normal_spoilage_rate__gte=0, normal_spoilage_rate__lte=100),
                name="ck_recipe_spoilage",
            ),
        ]


class FabricCatalogNode(models.Model):
    KIND_COUNTRY = "country"
    KIND_BRAND = "brand"
    KIND_COLOR = "color"
    KIND_TYPE = "type"
    KIND_CHOICES = [
        (KIND_COUNTRY, "کشور"),
        (KIND_BRAND, "برند"),
        (KIND_COLOR, "رنگ"),
        (KIND_TYPE, "جنس"),
    ]
    CHILD_KIND = {
        KIND_COUNTRY: KIND_BRAND,
        KIND_BRAND: KIND_COLOR,
        KIND_COLOR: KIND_TYPE,
    }

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    kind = models.CharField("نوع", max_length=20, choices=KIND_CHOICES, db_index=True)
    name = models.CharField("نام", max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "name", "id"]
        verbose_name = "گره کاتالوگ پارچه"
        verbose_name_plural = "گره‌های کاتالوگ پارچه"

    def __str__(self):
        return self.name
