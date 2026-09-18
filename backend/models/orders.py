"""Single-table order, line, payment schedule, and workflow."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from backend.soft_delete import SoftDeleteModel, SoftDeleteManager
from .base import MONEY_KWARGS, ReferenceCodeModel
from .config import (
    AccountingMode,
    Branch,
    InstallmentStatus,
    OrderKind,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from .people import Customer, Seller
from .workflow_cycle import Warehouse


class WorkflowStage(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    is_terminal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.code

    def __eq__(self, other):
        if isinstance(other, str):
            return self.code == other
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.pk)


class Sale(ReferenceCodeModel, SoftDeleteModel):
    reference_code_fields = {
        "payment_status": "payment_status_ref",
        "payment_method": "payment_method_ref",
        "accounting_mode": "accounting_mode_ref",
        "order_kind": "order_kind_ref",
        "order_status": "order_status_ref",
    }
    PAYMENT_METHOD_CHOICES = [("cash", "نقدی"), ("card", "کارت‌خوان"), ("check", "چک")]
    PAYMENT_STATUS_CHOICES = [
        ("paid", "پرداخت‌شده"),
        ("unpaid", "پرداخت‌نشده"),
        ("installment", "قسطی"),
    ]
    ORDER_KIND_CHOICES = [
        ("normal", "فروش و پرداخت آنی"),
        ("pre_invoice", "پیش‌فاکتور"),
        ("deposit", "بیعانیه"),
    ]
    ORDER_STATUS_CHOICES = [
        ("confirmed", "تایید شده"),
        ("pending", "در انتظار"),
        ("cancelled", "لغو شده"),
    ]
    DISCOUNT_TYPE_CHOICES = [
        ("percent", "درصدی"),
        ("amount", "مبلغ ثابت"),
        ("wallet", "موجودی حساب"),
        ("cashback", "کش‌بک"),
    ]
    ACCOUNTING_MODE_CHOICES = [("automatic", "حسابداری خودکار"), ("manual", "حسابداری دستی")]
    ORDER_KIND_NORMAL = "normal"
    ORDER_KIND_PRE_INVOICE = "pre_invoice"
    ORDER_KIND_DEPOSIT = "deposit"
    ORDER_STATUS_CONFIRMED = "confirmed"
    ORDER_STATUS_PENDING = "pending"
    ORDER_STATUS_CANCELLED = "cancelled"
    ACCOUNTING_MODE_AUTOMATIC = "automatic"
    ACCOUNTING_MODE_MANUAL = "manual"
    WORKFLOW_STAGE_PENDING_BRANCH = "pending_branch"
    WORKFLOW_STAGE_BRANCH_APPROVED = "branch_approved"
    WORKFLOW_STAGE_ACCOUNTING_APPROVED = "accounting_approved"
    WORKFLOW_STAGE_IN_PRODUCTION = "in_production"
    WORKFLOW_STAGE_PRODUCTION_DONE = "production_done"
    WORKFLOW_STAGE_IN_FREIGHT = "in_freight"
    WORKFLOW_STAGE_IN_WAREHOUSE = "in_warehouse"
    WORKFLOW_STAGE_READY_FOR_PICKUP = "ready_for_pickup"
    WORKFLOW_STAGE_MERCHANT_ASSIGNED = "merchant_assigned"
    WORKFLOW_STAGE_COMPLETED = "completed"
    WORKFLOW_STAGE_CHOICES = [
        (WORKFLOW_STAGE_PENDING_BRANCH, "منتظر سرپرست شعبه"),
        (WORKFLOW_STAGE_BRANCH_APPROVED, "منتظر حسابداری"),
        (WORKFLOW_STAGE_ACCOUNTING_APPROVED, "ارسال به کارخانه"),
        (WORKFLOW_STAGE_IN_PRODUCTION, "در حال ساخت"),
        (WORKFLOW_STAGE_PRODUCTION_DONE, "آماده باربری"),
        (WORKFLOW_STAGE_IN_FREIGHT, "در باربری"),
        (WORKFLOW_STAGE_IN_WAREHOUSE, "در انبار"),
        (WORKFLOW_STAGE_READY_FOR_PICKUP, "آماده تحویل حضوری"),
        (WORKFLOW_STAGE_MERCHANT_ASSIGNED, "بازرگان — صف کارخانه"),
        (WORKFLOW_STAGE_COMPLETED, "تکمیل شده"),
    ]
    FULFILLMENT_ROUTE_FACTORY = "factory"
    FULFILLMENT_ROUTE_WAREHOUSE = "warehouse"
    FULFILLMENT_ROUTE_PICKUP = "customer_pickup"
    FULFILLMENT_ROUTE_MERCHANT = "merchant"
    FULFILLMENT_ROUTE_CHOICES = [
        (FULFILLMENT_ROUTE_FACTORY, "کارخانه"),
        (FULFILLMENT_ROUTE_WAREHOUSE, "انبار"),
        (FULFILLMENT_ROUTE_PICKUP, "تحویل به مشتری"),
        (FULFILLMENT_ROUTE_MERCHANT, "بازرگان"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales")
    STOCK_SOURCE_WAREHOUSE = "warehouse"
    STOCK_SOURCE_BRANCH = "branch"
    STOCK_SOURCE_CHOICES = [
        (STOCK_SOURCE_WAREHOUSE, "انبار"),
        (STOCK_SOURCE_BRANCH, "شعبه"),
    ]

    branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="branch",
        default="branch_1",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    stock_source_kind = models.CharField(
        max_length=16, choices=STOCK_SOURCE_CHOICES, blank=True, default=""
    )
    stock_source_warehouse = models.ForeignKey(
        Warehouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_source_sales",
    )
    stock_source_branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="stock_source_branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_source_sales",
    )
    seller = models.ForeignKey(
        Seller, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales"
    )
    workflow_stage = models.ForeignKey(
        WorkflowStage,
        to_field="code",
        db_column="workflow_stage",
        default=WORKFLOW_STAGE_COMPLETED,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    amount = models.DecimalField(**MONEY_KWARGS)
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="amount"
    )
    discount_value = models.DecimalField(default=0, **MONEY_KWARGS)
    discount = models.DecimalField(default=0, **MONEY_KWARGS)
    final_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    paid_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    sold_at = models.DateTimeField(default=timezone.now)
    invoice_number = models.CharField(max_length=40, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    payment_status_ref = models.ForeignKey(
        PaymentStatus, db_column="payment_status", default="paid", on_delete=models.PROTECT
    )
    payment_method_ref = models.ForeignKey(
        PaymentMethod, db_column="payment_method", default="cash", on_delete=models.PROTECT
    )
    accounting_mode_ref = models.ForeignKey(
        AccountingMode,
        db_column="accounting_mode",
        default=ACCOUNTING_MODE_AUTOMATIC,
        on_delete=models.PROTECT,
    )
    order_kind_ref = models.ForeignKey(
        OrderKind, db_column="order_kind", default="normal", on_delete=models.PROTECT
    )
    order_status_ref = models.ForeignKey(
        OrderStatus, db_column="order_status", default="confirmed", on_delete=models.PROTECT
    )
    delivery_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_sales",
    )
    branch_approved_at = models.DateTimeField(null=True, blank=True)
    branch_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="branch_approved_sales",
    )
    accounting_approved_at = models.DateTimeField(null=True, blank=True)
    accounting_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_approved_sales",
    )
    factory_received_at = models.DateTimeField(null=True, blank=True)
    factory_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="factory_received_sales",
    )
    production_done_at = models.DateTimeField(null=True, blank=True)
    delivery_ready_at = models.DateTimeField(null=True, blank=True)
    delivery_ready_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_ready_sales",
    )
    early_disposition_required = models.BooleanField(default=False)
    early_ship_allowed_date = models.DateField(null=True, blank=True)
    early_disposition_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="early_disposition_sales",
    )
    shipped_early = models.BooleanField(default=False)
    freight_received_at = models.DateTimeField(null=True, blank=True)
    freight_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freight_received_sales",
    )
    freight_completed_at = models.DateTimeField(null=True, blank=True)
    office_released_at = models.DateTimeField(null=True, blank=True)
    factory_released_at = models.DateTimeField(null=True, blank=True)
    materials_deducted_at = models.DateTimeField(null=True, blank=True)
    fulfillment_route = models.CharField(
        max_length=32, choices=FULFILLMENT_ROUTE_CHOICES, null=True, blank=True
    )
    fulfillment_warehouse = models.ForeignKey(
        Warehouse,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfillment_orders",
    )
    fulfillment_source_branch = models.ForeignKey(
        Branch,
        to_field="code",
        db_column="fulfillment_source_branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fulfillment_source_orders",
    )
    merchant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="merchant_sales",
    )
    warehouse_completed_at = models.DateTimeField(null=True, blank=True)
    pickup_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sold_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="ck_order_amount"),
            models.CheckConstraint(condition=models.Q(discount__gte=0), name="ck_order_discount"),
            models.CheckConstraint(condition=models.Q(final_amount__gte=0), name="ck_order_final"),
            models.CheckConstraint(condition=models.Q(paid_amount__gte=0), name="ck_order_paid"),
            models.CheckConstraint(
                condition=models.Q(paid_amount__lte=models.F("final_amount")),
                name="ck_order_paid_lte_final",
            ),
            models.UniqueConstraint(
                fields=["branch", "invoice_number"],
                name="uq_order_branch_invoice",
            ),
        ]
        indexes = [
            models.Index(fields=["branch", "workflow_stage", "sold_at"], name="ix_order_queue"),
            models.Index(fields=["customer", "sold_at"], name="ix_order_customer_date"),
            models.Index(fields=["order_status_ref", "sold_at"], name="ix_order_status_date"),
        ]

    def __str__(self):
        return f"فاکتور {self.invoice_number or self.pk} - {self.final_amount}"

    def save(self, *args, **kwargs):
        if self.invoice_number == "":
            self.invoice_number = None
        return super().save(*args, **kwargs)

    def get_workflow_stage_display(self):
        return self.workflow_stage.label
    payment_status = property(
        lambda self: self.reference_code("payment_status"),
        lambda self, value: self.set_reference_code("payment_status", value),
    )
    payment_method = property(
        lambda self: self.reference_code("payment_method"),
        lambda self, value: self.set_reference_code("payment_method", value),
    )
    accounting_mode = property(
        lambda self: self.reference_code("accounting_mode"),
        lambda self, value: self.set_reference_code("accounting_mode", value),
    )
    order_kind = property(
        lambda self: self.reference_code("order_kind"),
        lambda self, value: self.set_reference_code("order_kind", value),
    )
    order_status = property(
        lambda self: self.reference_code("order_status"),
        lambda self, value: self.set_reference_code("order_status", value),
    )

    def get_payment_status_display(self):
        return self.reference_label("payment_status")

    def get_payment_method_display(self):
        return self.reference_label("payment_method")

    def get_accounting_mode_display(self):
        return self.reference_label("accounting_mode")

    def get_order_kind_display(self):
        return self.reference_label("order_kind")

    def get_order_status_display(self):
        return self.reference_label("order_status")


class SaleLineItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(
        "backend.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="sale_lines"
    )
    variant = models.ForeignKey(
        "backend.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sale_lines",
    )
    product_name = models.CharField(max_length=150)
    product_model = models.CharField(max_length=100, blank=True)
    fabric = models.CharField(max_length=100, blank=True)
    color_name = models.CharField(max_length=50, blank=True)
    color_hex = models.CharField(max_length=7, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1)
    unit_price = models.DecimalField(default=0, **MONEY_KWARGS)
    line_total = models.DecimalField(default=0, **MONEY_KWARGS)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_line_quantity"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_line_unit_price"),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="ck_line_total"),
        ]
        indexes = [models.Index(fields=["sale", "id"], name="ix_order_line_order")]


class SaleInstallment(ReferenceCodeModel, SoftDeleteModel):
    reference_code_fields = {
        "payment_method": "payment_method_ref",
        "status": "status_ref",
    }
    STATUS_CHOICES = [("pending", "در انتظار"), ("paid", "پرداخت‌شده"), ("cancelled", "لغوشده")]
    PAYMENT_METHOD_CHOICES = Sale.PAYMENT_METHOD_CHOICES
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="installments")
    amount = models.DecimalField(**MONEY_KWARGS)
    due_date = models.DateField()
    payment_method_ref = models.ForeignKey(
        PaymentMethod, db_column="payment_method", default="cash", on_delete=models.PROTECT
    )
    check_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    received_at = models.DateField(null=True, blank=True)
    receiver_name = models.CharField(max_length=120, blank=True)
    registration_account = models.ForeignKey(
        "backend.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="check_registrations",
    )
    deposit_account = models.ForeignKey(
        "backend.Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="check_deposits",
    )
    accounting_registered_at = models.DateTimeField(null=True, blank=True)
    accounting_entry = models.ForeignKey(
        "backend.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installment_checks",
    )
    status_ref = models.ForeignKey(
        InstallmentStatus, db_column="status", default="pending", on_delete=models.PROTECT
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_installment_amount"),
            models.CheckConstraint(
                condition=models.Q(payment_method_ref_id="check")
                | (models.Q(check_number="") & models.Q(bank_name="")),
                name="ck_installment_check_fields",
            ),
        ]
        indexes = [
            models.Index(fields=["status_ref", "due_date"], name="ix_installment_due"),
            models.Index(fields=["sale", "due_date"], name="ix_installment_order"),
        ]

    payment_method = property(
        lambda self: self.reference_code("payment_method"),
        lambda self, value: self.set_reference_code("payment_method", value),
    )
    status = property(
        lambda self: self.reference_code("status"),
        lambda self, value: self.set_reference_code("status", value),
    )

    def get_payment_method_display(self):
        return self.reference_label("payment_method")

    def get_status_display(self):
        return self.reference_label("status")


class OrderTransition(models.Model):
    order = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="transitions")
    from_stage = models.ForeignKey(
        WorkflowStage, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    to_stage = models.ForeignKey(
        WorkflowStage, on_delete=models.PROTECT, related_name="incoming_transitions"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    note = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["order", "occurred_at"], name="ix_transition_order_date"),
            models.Index(fields=["to_stage", "occurred_at"], name="ix_transition_stage_date"),
        ]


class OfficeOrderManager(SoftDeleteManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            workflow_stage_id__in=[
                Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
                Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
            ]
        )


class OfficeOrder(Sale):
    STATUS_PENDING = "pending_accounting"
    STATUS_RELEASED = "released_to_factory"
    STATUS_CHOICES = [(STATUS_PENDING, "منتظر تایید اداری"), (STATUS_RELEASED, "ارسال‌شده به کارخانه")]
    objects = OfficeOrderManager()

    class Meta:
        proxy = True

    @property
    def source_sale(self):
        return self

    @property
    def source_sale_id(self):
        return self.pk

    @property
    def status(self):
        return (
            self.STATUS_PENDING
            if self.workflow_stage_id == self.WORKFLOW_STAGE_BRANCH_APPROVED
            else self.STATUS_RELEASED
        )

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class FactoryOrderManager(SoftDeleteManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            workflow_stage_id__in=[
                Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
                Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
                Sale.WORKFLOW_STAGE_IN_PRODUCTION,
                Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
                Sale.WORKFLOW_STAGE_IN_FREIGHT,
                Sale.WORKFLOW_STAGE_COMPLETED,
            ]
        )


class FactoryOrder(Sale):
    WORKFLOW_STAGE_ACCOUNTING_APPROVED = Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED
    WORKFLOW_STAGE_MERCHANT_ASSIGNED = Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED
    WORKFLOW_STAGE_IN_PRODUCTION = Sale.WORKFLOW_STAGE_IN_PRODUCTION
    WORKFLOW_STAGE_PRODUCTION_DONE = Sale.WORKFLOW_STAGE_PRODUCTION_DONE
    WORKFLOW_STAGE_IN_FREIGHT = Sale.WORKFLOW_STAGE_IN_FREIGHT
    WORKFLOW_STAGE_COMPLETED = Sale.WORKFLOW_STAGE_COMPLETED
    WORKFLOW_STAGE_CHOICES = Sale.WORKFLOW_STAGE_CHOICES[2:]
    objects = FactoryOrderManager()

    class Meta:
        proxy = True

    @property
    def source_sale(self):
        return self

    @property
    def source_sale_id(self):
        return self.pk

    @property
    def source_office_order(self):
        return self

    @property
    def source_office_order_id(self):
        return self.pk


class OfficeOrderLineItem(SaleLineItem):
    class Meta:
        proxy = True

    @property
    def office_order(self):
        return self.sale

    @office_order.setter
    def office_order(self, value):
        self.sale = value

    @property
    def office_order_id(self):
        return self.sale_id


class FactoryOrderLineItem(SaleLineItem):
    class Meta:
        proxy = True

    @property
    def factory_order(self):
        return self.sale

    @factory_order.setter
    def factory_order(self, value):
        self.sale = value

    @property
    def factory_order_id(self):
        return self.sale_id


class OfficeOrderInstallment(SaleInstallment):
    class Meta:
        proxy = True

    @property
    def office_order(self):
        return self.sale

    @office_order.setter
    def office_order(self, value):
        self.sale = value

    @property
    def office_order_id(self):
        return self.sale_id


class FactoryOrderInstallment(SaleInstallment):
    class Meta:
        proxy = True
