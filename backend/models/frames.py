"""Frame (کلاف) catalog — models, wood requirements, and service templates."""

from django.db import models

from backend.soft_delete import SoftDeleteModel
from .base import QUANTITY_KWARGS


class FurnitureWorkset(SoftDeleteModel):
    """دست مبلمان — ترکیب قطعات با تعداد."""

    name = models.CharField("نام دست", max_length=150)
    design_style = models.CharField("سبک طراحی", max_length=32, blank=True, default="")
    seat_count = models.PositiveIntegerField("تعداد نفر", null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FurnitureWorksetPiece(models.Model):
    """یک نوع قطعه با تعداد داخل دست."""

    workset = models.ForeignKey(
        FurnitureWorkset,
        on_delete=models.CASCADE,
        related_name="pieces",
    )
    piece_kind = models.CharField("نوع قطعه", max_length=32)
    arm_style = models.CharField("حالت دسته", max_length=16)
    quantity = models.PositiveIntegerField("تعداد", default=1)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workset", "piece_kind", "arm_style"],
                name="uq_workset_piece_arm",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_workset_piece_qty"),
        ]

    def __str__(self):
        return f"{self.workset_id}:{self.piece_kind}:{self.arm_style}×{self.quantity}"


class Frame(SoftDeleteModel):
    DESIGN_MODERN = "modern"
    DESIGN_CLASSIC = "classic"
    DESIGN_NEO_CLASSIC = "neo_classic"
    DESIGN_MINIMAL = "minimal"
    DESIGN_AVANT_GARDE = "avant_garde"
    DESIGN_STYLE_CHOICES = [
        (DESIGN_MODERN, "مدرن"),
        (DESIGN_CLASSIC, "کلاسیک"),
        (DESIGN_NEO_CLASSIC, "نیو کلاسیک"),
        (DESIGN_MINIMAL, "مینیمال"),
        (DESIGN_AVANT_GARDE, "اوانگارد"),
    ]

    WOOD_ASH_GEORGIAN_G1 = "ash_georgian_g1"
    WOOD_OAK = "oak"
    WOOD_WALNUT = "walnut"
    WOOD_RUSSIAN = "russian"
    WOOD_TUSCA = "tusca"
    WOOD_ASH_RUSSIAN_MIX = "ash_russian_mix"
    WOOD_TYPE_CHOICES = [
        (WOOD_ASH_GEORGIAN_G1, "راش گرجستان درجه ۱"),
        (WOOD_OAK, "بلوط"),
        (WOOD_WALNUT, "گردو"),
        (WOOD_RUSSIAN, "روس"),
        (WOOD_TUSCA, "توسکا"),
        (WOOD_ASH_RUSSIAN_MIX, "ترکیب راش و روس"),
    ]

    PIECE_ARMCHAIR = "armchair"
    PIECE_SOFA_2 = "sofa_2"
    PIECE_SOFA_3 = "sofa_3"
    PIECE_SOFA_4 = "sofa_4"
    PIECE_SOFA_5 = "sofa_5"
    PIECE_CHAISE = "chaise"
    PIECE_POUF = "pouf"
    PIECE_BENCH = "bench"
    PIECE_LOVESEAT = "loveseat"
    PIECE_SIDE_TABLE = "side_table"
    PIECE_COFFEE_TABLE = "coffee_table"
    PIECE_KIND_CHOICES = [
        (PIECE_ARMCHAIR, "مبل تک"),
        (PIECE_SOFA_2, "کاناپه ۲ نفره"),
        (PIECE_SOFA_3, "کاناپه ۳ نفره"),
        (PIECE_SOFA_4, "کاناپه ۴ نفره"),
        (PIECE_SOFA_5, "کاناپه ۵ نفره"),
        (PIECE_CHAISE, "شزلون"),
        (PIECE_POUF, "پاف"),
        (PIECE_BENCH, "بنچ"),
        (PIECE_LOVESEAT, "لاو ست"),
        (PIECE_SIDE_TABLE, "کنار مبلی"),
        (PIECE_COFFEE_TABLE, "جلو مبلی"),
    ]

    ARM_NONE = "none"
    ARM_ONE = "one"
    ARM_TWO = "two"
    ARM_ONE_LEFT = "one_left"
    ARM_ONE_RIGHT = "one_right"
    ARM_STYLE_CHOICES = [
        (ARM_NONE, "بدون دسته"),
        (ARM_ONE, "تک‌دسته"),
        (ARM_TWO, "دو دسته"),
        (ARM_ONE_LEFT, "تک‌دسته چپ"),
        (ARM_ONE_RIGHT, "تک‌دسته راست"),
    ]

    workset = models.ForeignKey(
        FurnitureWorkset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="frames",
    )
    piece_kind = models.CharField("نوع قطعه", max_length=32, blank=True, default="")
    arm_style = models.CharField("حالت دسته", max_length=16, blank=True, default="")
    name = models.CharField("نام کلاف", max_length=150)
    design_style = models.CharField(
        "سبک طراحی", max_length=32, choices=DESIGN_STYLE_CHOICES, default=DESIGN_MODERN
    )
    wood_type = models.CharField(
        "جنس چوب اصلی", max_length=32, choices=WOOD_TYPE_CHOICES, default=WOOD_ASH_GEORGIAN_G1
    )
    product = models.ForeignKey(
        "backend.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="frames",
    )
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FrameModel(models.Model):
    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name="models")
    name = models.CharField("نام مدل", max_length=100)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["frame", "name"], name="uq_frame_model_name"),
        ]

    def __str__(self):
        return f"{self.frame.name} — {self.name}"


class FrameWoodRequirement(models.Model):
    UNIT_METER = "متر"
    UNIT_PIECE = "عدد"
    UNIT_CHOICES = [(UNIT_METER, "متر"), (UNIT_PIECE, "عدد")]

    frame_model = models.ForeignKey(
        FrameModel, on_delete=models.CASCADE, related_name="wood_requirements"
    )
    label = models.CharField("برچسب", max_length=100, blank=True)
    quantity = models.DecimalField("مقدار", default=1, **QUANTITY_KWARGS)
    unit = models.CharField("واحد", max_length=20, choices=UNIT_CHOICES, default=UNIT_METER)
    material = models.ForeignKey(
        "backend.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="frame_wood_requirements",
    )
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_frame_wood_qty"),
        ]


class FrameServiceTemplate(models.Model):
    frame = models.OneToOneField(Frame, on_delete=models.CASCADE, related_name="service_template")
    name = models.CharField("نام سرویس", max_length=100, default="سرویس ۸ نفره")
    default_seat_count = models.PositiveIntegerField("تعداد نفر پیش‌فرض", default=8)

    class Meta:
        ordering = ["frame_id"]

    def __str__(self):
        return f"{self.frame.name} — {self.name}"


class FrameServiceComponent(models.Model):
    TYPE_THREE_SEATER = "three_seater"
    TYPE_ARMCHAIR = "armchair"
    TYPE_SIDE_TABLE = "side_table"
    TYPE_COFFEE_TABLE = "coffee_table"
    COMPONENT_TYPE_CHOICES = [
        (TYPE_THREE_SEATER, "کاناپه ۳ نفره"),
        (TYPE_ARMCHAIR, "مبل تک‌نفره"),
        (TYPE_SIDE_TABLE, "کنار مبل"),
        (TYPE_COFFEE_TABLE, "جلو مبل"),
    ]
    DEFAULT_QUANTITIES = {
        TYPE_THREE_SEATER: 1,
        TYPE_ARMCHAIR: 2,
        TYPE_SIDE_TABLE: 2,
        TYPE_COFFEE_TABLE: 1,
    }

    template = models.ForeignKey(
        FrameServiceTemplate, on_delete=models.CASCADE, related_name="components"
    )
    component_type = models.CharField("نوع قطعه", max_length=32, choices=COMPONENT_TYPE_CHOICES)
    default_quantity = models.PositiveIntegerField("تعداد پیش‌فرض", default=1)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "component_type"],
                name="uq_frame_service_component_type",
            ),
        ]


class FrameComponentMaterialRule(models.Model):
    RULE_BACK_FABRIC = "back_fabric"
    RULE_BACK_WOOD = "back_wood"
    RULE_EXTRA = "extra"
    RULE_KEY_CHOICES = [
        (RULE_BACK_FABRIC, "پشت پارچه"),
        (RULE_BACK_WOOD, "پشت چوب"),
        (RULE_EXTRA, "متریال اضافه"),
    ]

    component = models.ForeignKey(
        FrameServiceComponent, on_delete=models.CASCADE, related_name="material_rules"
    )
    rule_key = models.CharField("نوع قانون", max_length=32, choices=RULE_KEY_CHOICES)
    material = models.ForeignKey(
        "backend.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="frame_component_rules",
    )
    quantity = models.DecimalField("مقدار", default=1, **QUANTITY_KWARGS)
    unit = models.CharField("واحد", max_length=20, default="متر")
    is_default = models.BooleanField("پیش‌فرض", default=False)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_frame_rule_qty"),
        ]
