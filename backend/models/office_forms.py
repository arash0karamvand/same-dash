"""مدل‌های فرم‌های اداری - مساعده، تنخواه، جابجایی انبار، سفارش تولید، تایید کارکرد"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from backend.soft_delete import SoftDeleteModel
from .base import MONEY_KWARGS, ReferenceCodeModel
from .workflow_cycle import Warehouse


class AssistanceRequest(ReferenceCodeModel, SoftDeleteModel):
    """درخواست مساعده کارکنان"""
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار تایید"),
        (STATUS_APPROVED, "تایید شده"),
        (STATUS_REJECTED, "رد شده"),
        (STATUS_PAID, "پرداخت شده"),
    ]
    
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assistance_requests"
    )
    national_code = models.CharField(max_length=10, blank=True)
    department = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(**MONEY_KWARGS)
    reason = models.TextField(blank=True)
    request_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    approval_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_assistance_requests"
    )
    payment_date = models.DateField(null=True, blank=True)
    journal = models.ForeignKey(
        "backend.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assistance_requests",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-request_date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["status", "request_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="ck_assistance_amount_positive"
            ),
        ]
    
    def __str__(self):
        return f"مساعده {self.employee.get_full_name()} - {self.amount:,} ریال"


class PettyCashRequest(ReferenceCodeModel, SoftDeleteModel):
    """تنخواه - درخواست پرداخت نقدی جزئی"""
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PAID = "paid"
    STATUS_SETTLED = "settled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار تایید"),
        (STATUS_APPROVED, "تایید شده"),
        (STATUS_REJECTED, "رد شده"),
        (STATUS_PAID, "پرداخت شده"),
        (STATUS_SETTLED, "تسویه شده"),
    ]
    
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="petty_cash_requests"
    )
    amount = models.DecimalField(**MONEY_KWARGS)
    purpose = models.TextField()
    request_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_petty_cash_requests"
    )
    approval_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    settlement_date = models.DateField(null=True, blank=True)
    settlement_amount = models.DecimalField(null=True, blank=True, **MONEY_KWARGS)
    journal = models.ForeignKey(
        "backend.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="petty_cash_requests",
    )
    settlement_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-request_date", "-created_at"]
        indexes = [
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["status", "request_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="ck_petty_cash_amount_positive"
            ),
        ]
    
    def __str__(self):
        return f"تنخواه {self.requester.get_full_name()} - {self.amount:,} ریال"


class WarehouseTransfer(ReferenceCodeModel, SoftDeleteModel):
    """جابجایی محصول بین انبارها یا نمایشگاه‌ها"""
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار تایید"),
        (STATUS_APPROVED, "تایید شده"),
        (STATUS_IN_TRANSIT, "در حال انتقال"),
        (STATUS_COMPLETED, "تکمیل شده"),
        (STATUS_CANCELLED, "لغو شده"),
    ]
    
    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transfers_out"
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transfers_in"
    )
    transfer_date = models.DateField()
    required_personnel = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_transfers"
    )
    approved_by_sales = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_approved_transfers"
    )
    approved_by_qc = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="qc_approved_transfers"
    )
    approved_by_production = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_approved_transfers"
    )
    qc_approved = models.BooleanField(default=False)
    qc_notes = models.TextField(blank=True)
    has_defects = models.BooleanField(default=False)
    defect_description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-transfer_date", "-created_at"]
        indexes = [
            models.Index(fields=["from_warehouse", "to_warehouse", "status"]),
            models.Index(fields=["status", "transfer_date"]),
        ]
    
    def __str__(self):
        return f"جابجایی از {self.from_warehouse} به {self.to_warehouse} - {self.transfer_date}"


class WarehouseTransferLine(models.Model):
    """آیتم‌های جابجایی انبار"""
    
    transfer = models.ForeignKey(
        WarehouseTransfer,
        on_delete=models.CASCADE,
        related_name="lines"
    )
    product_code = models.CharField(max_length=100)
    product_description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, default="عدد")
    notes = models.TextField(blank=True)
    line_number = models.PositiveIntegerField()
    
    class Meta:
        ordering = ["transfer", "line_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "line_number"],
                name="uq_transfer_line"
            ),
        ]
    
    def __str__(self):
        return f"{self.product_description} - {self.quantity} {self.unit}"


class ProductionOrder(ReferenceCodeModel, SoftDeleteModel):
    """سفارش تولید - لینک به Sale برای تولید محصول"""
    
    PRIORITY_WHITE = "white"
    PRIORITY_YELLOW = "yellow"
    PRIORITY_RED = "red"
    PRIORITY_CHOICES = [
        (PRIORITY_WHITE, "سفید - عادی"),
        (PRIORITY_YELLOW, "زرد - فوری"),
        (PRIORITY_RED, "قرمز - بسیار فوری"),
    ]
    
    ORDER_TYPE_PRODUCTION = "production"
    ORDER_TYPE_SERVICE = "service"
    ORDER_TYPE_CORRECTION = "correction"
    ORDER_TYPE_CHOICES = [
        (ORDER_TYPE_PRODUCTION, "سفارش تولید"),
        (ORDER_TYPE_SERVICE, "سفارش خدمات"),
        (ORDER_TYPE_CORRECTION, "اصلاحیه سفارش"),
    ]
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_IN_PRODUCTION = "in_production"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار تایید"),
        (STATUS_APPROVED, "تایید شده"),
        (STATUS_IN_PRODUCTION, "در حال تولید"),
        (STATUS_COMPLETED, "تکمیل شده"),
        (STATUS_CANCELLED, "لغو شده"),
    ]
    
    sale = models.ForeignKey(
        "Sale",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="production_orders"
    )
    invoice_number = models.CharField(max_length=50, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    branch_name = models.CharField(max_length=100, blank=True)
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        default=ORDER_TYPE_PRODUCTION
    )
    order_date = models.DateField(default=timezone.now)
    delivery_date = models.DateField()
    announcement_date = models.DateField(null=True, blank=True)
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_WHITE
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    product_model = models.CharField(max_length=200, blank=True)
    product_name = models.CharField(max_length=200, blank=True)
    cushion_notes = models.TextField(blank=True)
    general_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_production_orders"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_production_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    class Meta:
        ordering = ["-delivery_date", "-order_date"]
        indexes = [
            models.Index(fields=["status", "priority", "delivery_date"]),
            models.Index(fields=["sale"]),
        ]
    
    def __str__(self):
        return f"سفارش تولید {self.reference_code} - {self.customer_name}"


class ProductionOrderLine(models.Model):
    """جزئیات آیتم‌های سفارش تولید"""
    
    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    quantity = models.IntegerField(default=1)
    wood_color = models.CharField(max_length=100, blank=True)
    panel_color = models.CharField(max_length=100, blank=True)
    fabric_color = models.CharField(max_length=100, blank=True)
    fabric_quality = models.CharField(max_length=100, blank=True)
    fabric_code = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ["production_order", "line_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["production_order", "line_number"],
                name="uq_production_order_line"
            ),
        ]
    
    def __str__(self):
        return f"ردیف {self.line_number} - {self.quantity} عدد"


class AttendanceConfirmation(ReferenceCodeModel, SoftDeleteModel):
    """تایید کارکرد ماهانه کارکنان"""
    
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار تایید"),
        (STATUS_CONFIRMED, "تایید شده"),
        (STATUS_REJECTED, "رد شده"),
    ]
    
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_confirmations"
    )
    month = models.CharField(max_length=7)  # Format: "1403-09"
    year = models.IntegerField()
    month_number = models.IntegerField()
    days_worked = models.IntegerField(default=0)
    overtime_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0")
    )
    absence_days = models.IntegerField(default=0)
    leave_days = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_attendances"
    )
    confirmation_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-year", "-month_number", "employee"]
        indexes = [
            models.Index(fields=["employee", "year", "month_number"]),
            models.Index(fields=["status", "year", "month_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "year", "month_number"],
                name="uq_attendance_employee_month"
            ),
            models.CheckConstraint(
                condition=models.Q(days_worked__gte=0) & models.Q(days_worked__lte=31),
                name="ck_days_worked_range"
            ),
            models.CheckConstraint(
                condition=models.Q(overtime_hours__gte=0),
                name="ck_overtime_positive"
            ),
        ]
    
    def __str__(self):
        return f"کارکرد {self.employee.get_full_name()} - {self.month}"
