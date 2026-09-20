"""Customers, organization, staff, and attendance."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from backend.soft_delete import SoftDeleteModel
from .base import MONEY_KWARGS, ReferenceCodeModel
from .config import ApprovalStatus, AttendanceStatus, Branch


class LoyaltyLevel(SoftDeleteModel):
    name = models.CharField(max_length=50, unique=True)
    min_purchase = models.DecimalField(default=0, **MONEY_KWARGS)
    max_purchase = models.DecimalField(null=True, blank=True, **MONEY_KWARGS)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    points = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#6366f1")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["min_purchase"]
        constraints = [
            models.CheckConstraint(condition=models.Q(min_purchase__gte=0), name="ck_level_min"),
            models.CheckConstraint(
                condition=models.Q(max_purchase__isnull=True)
                | models.Q(max_purchase__gte=models.F("min_purchase")),
                name="ck_level_range",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0)
                & models.Q(discount_percent__lte=100),
                name="ck_level_discount",
            ),
        ]

    def __str__(self):
        return self.name


class Customer(SoftDeleteModel):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, unique=True)
    membership_code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    level = models.ForeignKey(
        LoyaltyLevel, null=True, blank=True, on_delete=models.SET_NULL, related_name="customers"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-joined_at"]
        indexes = [models.Index(fields=["is_active", "joined_at"], name="ix_customer_active_join")]

    @property
    def wallet_balance(self):
        return self.wallet_transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def cashback_balance(self):
        return self.cashback_transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def total_purchases(self):
        """Paid purchases backed by active, balanced sale/payment journals."""
        from .accounting import JournalEntry, JournalLine

        total = Decimal("0")
        sales = self.sales.exclude(order_status_ref_id="cancelled")
        for sale in sales:
            receipts = JournalLine.objects.filter(
                journal__order_links__order=sale,
                account__slug__in={
                    "cash_documents",
                    "petty_cash",
                    "bank",
                    "collection_at_bank",
                },
            ).exclude(
                journal__status_ref_id=JournalEntry.STATUS_VOID
            ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
            receipts = Decimal(receipts["debit"] or 0) - Decimal(receipts["credit"] or 0)
            total += max(
                Decimal("0"),
                min(Decimal(sale.paid_amount or 0), receipts),
            )
        return total

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class OrgRank(models.Model):
    name = models.CharField(max_length=80)
    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="org_ranks",
    )
    color = models.CharField(max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "branch"], name="uq_rank_name_branch"),
        ]

    def __str__(self):
        return self.name


class StaffProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile"
    )
    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="branch",
        default="branch_1",
        on_delete=models.PROTECT,
        related_name="staff_profiles",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
    )
    job_title = models.CharField(max_length=100, blank=True)
    org_rank = models.ForeignKey(
        OrgRank, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff_members"
    )

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def get_branch_display(self):
        return self.branch.label


class Seller(SoftDeleteModel):
    STAFF_KIND_SELLER = "seller"
    STAFF_KIND_MANAGER = "manager"
    STAFF_KIND_CHOICES = [(STAFF_KIND_SELLER, "فروشنده"), (STAFF_KIND_MANAGER, "مدیر")]

    full_name = models.CharField(max_length=150)
    staff_kind = models.CharField(
        max_length=20, choices=STAFF_KIND_CHOICES, default=STAFF_KIND_SELLER, db_index=True
    )
    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="branch",
        default="branch_1",
        on_delete=models.PROTECT,
        related_name="sellers",
    )
    phone = models.CharField(max_length=20, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seller_profile",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class StaffAttendance(ReferenceCodeModel, SoftDeleteModel):
    reference_code_fields = {
        "status": "status_ref",
        "approval_status": "approval_status_ref",
    }
    STATUS_CHOICES = [("present", "حاضر"), ("absent", "غایب"), ("leave", "مرخصی"), ("mission", "ماموریت")]
    LEAVE_PAY_PAID = "paid"
    LEAVE_PAY_UNPAID = "unpaid"
    LEAVE_PAY_CHOICES = [(LEAVE_PAY_PAID, "با حقوق"), (LEAVE_PAY_UNPAID, "بدون حقوق")]
    MISSION_DEST_BRANCH = "branch"
    MISSION_DEST_WAREHOUSE = "warehouse"
    MISSION_DEST_FACTORY = "factory"
    MISSION_DEST_OUTSIDE = "outside"
    MISSION_DEST_CHOICES = [
        (MISSION_DEST_BRANCH, "شعبه"),
        (MISSION_DEST_WAREHOUSE, "انبار"),
        (MISSION_DEST_FACTORY, "کارخانه"),
        (MISSION_DEST_OUTSIDE, "خارج از شرکت"),
    ]
    APPROVAL_CHOICES = [
        ("pending", "در انتظار تایید"),
        ("approved", "تایید شده"),
        ("rejected", "رد شده"),
    ]
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    status_ref = models.ForeignKey(
        AttendanceStatus, db_column="status", default="present", on_delete=models.PROTECT
    )
    work_branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="work_branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    approval_status_ref = models.ForeignKey(
        ApprovalStatus,
        db_column="approval_status",
        default="approved",
        on_delete=models.PROTECT,
    )
    notes = models.CharField(max_length=255, blank=True)
    leave_pay_type = models.CharField(max_length=16, blank=True, choices=LEAVE_PAY_CHOICES)
    leave_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    mission_dest_kind = models.CharField(max_length=20, blank=True, choices=MISSION_DEST_CHOICES)
    mission_dest_code = models.CharField(max_length=80, blank=True)
    mission_dest_label = models.CharField(max_length=160, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_attendance",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            # MariaDB ignores partial unique indexes (W036); check_in() is the real guard.
            models.UniqueConstraint(
                fields=["seller"],
                condition=models.Q(
                    check_out_at__isnull=True,
                    is_deleted=False,
                    status_ref="present",
                ),
                name="uq_seller_open_present_attendance",
            ),
            models.CheckConstraint(
                condition=models.Q(check_out_at__isnull=True)
                | models.Q(check_in_at__isnull=False),
                name="ck_attendance_checkout",
            ),
        ]

    @classmethod
    def check(cls, **kwargs):
        return [error for error in super().check(**kwargs) if getattr(error, "id", None) != "models.W036"]

    status = property(
        lambda self: self.reference_code("status"),
        lambda self, value: self.set_reference_code("status", value),
    )
    approval_status = property(
        lambda self: self.reference_code("approval_status"),
        lambda self, value: self.set_reference_code("approval_status", value),
    )

    def get_status_display(self):
        return self.reference_label("status")

    def get_approval_status_display(self):
        return self.reference_label("approval_status")


CustomerAttendance = StaffAttendance


class CustomerLevelHistory(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="level_history")
    previous_level = models.ForeignKey(
        LoyaltyLevel, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    new_level = models.ForeignKey(
        LoyaltyLevel, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)
    total_purchases_at_change = models.DecimalField(default=0, **MONEY_KWARGS)

    class Meta:
        ordering = ["-changed_at"]
