"""Configurable sale cycle: slots, assignees, and warehouses."""

from django.conf import settings
from django.db import models

from .config import Branch
from .people import OrgRank


class Warehouse(models.Model):
    code = models.SlugField("کد انبار", max_length=40, unique=True)
    label = models.CharField("نام انبار", max_length=80)
    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warehouses",
    )
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class OrderCycle(models.Model):
    name = models.CharField(max_length=80, default="چرخه فروش")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "id"]

    def __str__(self):
        return self.name


class CycleSlot(models.Model):
    ASSIGNEE_USER = "user"
    ASSIGNEE_RANK = "rank"
    ASSIGNEE_NONE = ""
    ASSIGNEE_TYPE_CHOICES = [
        (ASSIGNEE_NONE, "تعیین‌نشده"),
        (ASSIGNEE_USER, "کاربر"),
        (ASSIGNEE_RANK, "مقام"),
    ]

    KIND_FIXED = "fixed"
    KIND_MONITOR = "monitor"
    KIND_ROUTE = "route"
    KIND_CHOICES = [
        (KIND_FIXED, "مرحله ثابت"),
        (KIND_MONITOR, "نظارت"),
        (KIND_ROUTE, "مسیر ارسال"),
    ]

    cycle = models.ForeignKey(OrderCycle, on_delete=models.CASCADE, related_name="slots")
    step_key = models.SlugField(max_length=40)
    label = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_FIXED)
    assignee_type = models.CharField(
        max_length=10, choices=ASSIGNEE_TYPE_CHOICES, blank=True, default=""
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cycle_slots",
    )
    org_rank = models.ForeignKey(
        OrgRank,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cycle_slots",
    )
    is_enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "step_key"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "step_key"], name="uq_cycle_step_key"),
        ]

    def __str__(self):
        return f"{self.cycle_id}:{self.step_key}"
