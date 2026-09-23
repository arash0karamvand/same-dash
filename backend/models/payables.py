"""حساب‌های پرداختنی کارخانه — تامین‌کننده، فاکتور خرید، چک و تسویه."""

from django.conf import settings
from django.db import models

from .base import MONEY_KWARGS, QUANTITY_KWARGS


class MaterialSupplier(models.Model):
    """تامین‌کننده مواد اولیه. هر تامین‌کننده یک حساب معین زیر حساب‌های پرداختنی دارد."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    national_id = models.CharField(max_length=20, blank=True, default="")
    address = models.CharField(max_length=300, blank=True, default="")
    credit_days = models.PositiveSmallIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    account = models.OneToOneField(
        "backend.Account", on_delete=models.PROTECT, related_name="material_supplier"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(credit_days__lte=365), name="ck_supplier_credit_days"),
        ]

    def __str__(self):
        return self.name


class PurchaseInvoice(models.Model):
    """فاکتور خرید مواد. با ورود به انبار، سند موجودی / تامین‌کننده صادر می‌شود."""

    STATUS_OPEN = "open"
    STATUS_PARTIAL = "partial"
    STATUS_SETTLED = "settled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "باز"),
        (STATUS_PARTIAL, "تسویه ناقص"),
        (STATUS_SETTLED, "تسویه‌شده"),
    ]

    supplier = models.ForeignKey(MaterialSupplier, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=60)
    warehouse_receipt = models.CharField(max_length=60)
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN)
    goods_net = models.DecimalField(default=0, **MONEY_KWARGS)
    charges = models.DecimalField(default=0, **MONEY_KWARGS)
    inventory_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    vat_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    payable_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    settled_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    description = models.CharField(max_length=300, blank=True, default="")
    journal = models.ForeignKey(
        "backend.JournalEntry", on_delete=models.PROTECT, related_name="purchase_invoices"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_invoices"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "invoice_number"], name="uq_ap_invoice_number"),
            models.CheckConstraint(condition=models.Q(payable_amount__gt=0), name="ck_ap_invoice_payable"),
            models.CheckConstraint(condition=models.Q(settled_amount__gte=0), name="ck_ap_invoice_settled"),
            models.CheckConstraint(condition=models.Q(vat_rate__gte=0), name="ck_ap_invoice_vat"),
        ]
        indexes = [models.Index(fields=["status", "due_date"], name="ix_ap_invoice_due")]

    def __str__(self):
        return self.invoice_number


class PurchaseInvoiceLine(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey("backend.Material", on_delete=models.PROTECT, related_name="purchase_invoice_lines")
    quantity = models.DecimalField(**QUANTITY_KWARGS)
    unit_price = models.DecimalField(default=0, **MONEY_KWARGS)
    trade_discount = models.DecimalField(default=0, **MONEY_KWARGS)
    goods_net = models.DecimalField(default=0, **MONEY_KWARGS)
    inventory_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    unit_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    inventory_move = models.ForeignKey(
        "backend.InventoryTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_invoice_lines",
    )
    line_number = models.PositiveIntegerField()

    class Meta:
        ordering = ["invoice", "line_number"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "line_number"], name="uq_ap_invoice_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_ap_line_qty"),
        ]


class PayableSettlement(models.Model):
    """تسویه یک یا چند فاکتور با چک، بانک یا صندوق."""

    KIND_CHECK = "check"
    KIND_BANK = "bank"
    KIND_CASH = "cash"
    KIND_CHOICES = [
        (KIND_CHECK, "چک"),
        (KIND_BANK, "بانک"),
        (KIND_CASH, "صندوق"),
    ]

    supplier = models.ForeignKey(MaterialSupplier, on_delete=models.PROTECT, related_name="settlements")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount = models.DecimalField(**MONEY_KWARGS)
    settled_on = models.DateField()
    is_void = models.BooleanField(default=False)
    journal = models.ForeignKey(
        "backend.JournalEntry", on_delete=models.PROTECT, related_name="payable_settlements"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payable_settlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-settled_on", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_ap_settlement_amount"),
        ]


class PayableCheck(models.Model):
    """چک پرداختی به تامین‌کننده. تا پاس شدن، در اسناد پرداختنی می‌ماند."""

    STATUS_ISSUED = "issued"
    STATUS_CLEARED = "cleared"
    STATUS_VOID = "void"
    STATUS_CHOICES = [
        (STATUS_ISSUED, "صادرشده"),
        (STATUS_CLEARED, "پاس‌شده"),
        (STATUS_VOID, "باطل"),
    ]

    supplier = models.ForeignKey(MaterialSupplier, on_delete=models.PROTECT, related_name="checks")
    settlement = models.OneToOneField(PayableSettlement, on_delete=models.PROTECT, related_name="issued_check")
    check_number = models.CharField(max_length=40)
    bank_name = models.CharField(max_length=80)
    amount = models.DecimalField(**MONEY_KWARGS)
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    clear_journal = models.ForeignKey(
        "backend.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cleared_payable_checks",
    )
    cleared_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "check_number"], name="uq_ap_check_number"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_ap_check_amount"),
        ]
        indexes = [models.Index(fields=["status", "due_date"], name="ix_ap_check_due")]

    def __str__(self):
        return self.check_number


class PayableAllocation(models.Model):
    """سهم هر فاکتور از یک تسویه."""

    settlement = models.ForeignKey(PayableSettlement, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(**MONEY_KWARGS)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["settlement", "invoice"], name="uq_ap_allocation_invoice"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_ap_allocation_amount"),
        ]
