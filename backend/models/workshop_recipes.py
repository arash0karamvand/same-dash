"""دستورهای دست‌کار کارخانه — رنگ، پارچه، فوم، کوسن."""

from django.db import models

from backend.soft_delete import SoftDeleteModel
from .base import QUANTITY_KWARGS


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

    kind = models.CharField("نوع دستور", max_length=20, choices=KIND_CHOICES, db_index=True)
    name = models.CharField("نام", max_length=150)
    color_name = models.CharField("رنگ / فام", max_length=80, blank=True, default="")
    note = models.TextField("توضیحات", blank=True, default="")
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = "دستور دست‌کار"
        verbose_name_plural = "دستورهای دست‌کار"

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
    unit = models.CharField("واحد", max_length=20, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "متریال دستور دست‌کار"
        verbose_name_plural = "متریال‌های دستور دست‌کار"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "material"], name="uq_workshop_recipe_material"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_workshop_recipe_qty"),
        ]
