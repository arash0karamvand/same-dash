"""دفتر دوطرفه: کدینگ، سرفصل سند و آرتیکل.

لایه مدل (MVC). کنترل صدور در logic.document_issuance است.
GenericForeignKey جنگو اینجا استفاده نشده؛ InnoDB برای آن کلید خارجی نمی‌سازد.
اتصال به UUID فروش، کارخانه و انبار از AccountingOrigin با قوس انحصاری است.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .base import MONEY_KWARGS, QUANTITY_KWARGS, ReferenceCodeModel, ReferenceQuerySet
from .config import JournalEntryStatus, JournalEntryType

_defer_closure_rebuild = ContextVar("defer_closure_rebuild", default=0)


@contextmanager
def defer_account_closure_rebuild():
    """Bulk account writes — rebuild closure table once at end."""
    token = _defer_closure_rebuild.set(_defer_closure_rebuild.get() + 1)
    try:
        yield
    finally:
        _defer_closure_rebuild.reset(token)
        if _defer_closure_rebuild.get() == 0:
            _rebuild_account_closure()


class Ledger(models.Model):
    KIND_OFFICE = "office"
    KIND_FACTORY = "factory"
    KIND_CHOICES = [(KIND_OFFICE, "اداری"), (KIND_FACTORY, "کارخانه")]
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Account(models.Model):
    """کدینگ حساب‌ها — درخت گروه / کل / معین / تفصیلی."""

    CLASS_CHOICES = [
        ("asset", "دارایی"),
        ("liability", "بدهی"),
        ("equity", "سرمایه"),
        ("revenue", "درآمد"),
        ("expense", "هزینه"),
    ]
    NORMAL_BALANCE_CHOICES = [("debit", "بدهکار"), ("credit", "بستانکار")]
    LEVEL_GROUP = 1
    LEVEL_GENERAL = 2
    LEVEL_SUBSIDIARY = 3
    LEVEL_DETAIL = 4
    MAX_LEVEL = 4
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="accounts")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    slug = models.SlugField(max_length=60)
    code = models.CharField(max_length=30)
    path = models.CharField(max_length=255, editable=False)
    name = models.CharField(max_length=120)
    account_class = models.CharField(max_length=20, choices=CLASS_CHOICES)
    normal_balance = models.CharField(max_length=10, choices=NORMAL_BALANCE_CHOICES)
    sort_order = models.PositiveSmallIntegerField(default=0)
    legacy_entry_type = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["ledger", "sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["ledger", "slug"], name="uq_account_ledger_slug"),
            models.UniqueConstraint(fields=["ledger", "path"], name="uq_account_ledger_path"),
            models.CheckConstraint(condition=~models.Q(code=""), name="ck_account_code_nonempty"),
            models.CheckConstraint(
                condition=models.Q(account_class__in=["asset", "liability", "equity", "revenue", "expense"]),
                name="ck_account_class",
            ),
            models.CheckConstraint(
                condition=models.Q(normal_balance__in=["debit", "credit"]),
                name="ck_account_normal_balance",
            ),
        ]
        indexes = [
            models.Index(fields=["ledger", "parent", "sort_order"], name="ix_account_tree"),
        ]

    @property
    def full_code(self):
        return self.path

    @property
    def level(self):
        depth = self.LEVEL_GROUP
        parent_id = self.parent_id
        seen = set()
        while parent_id and parent_id not in seen and depth < self.MAX_LEVEL:
            seen.add(parent_id)
            depth += 1
            parent_id = (
                type(self).objects.filter(pk=parent_id).values_list("parent_id", flat=True).first()
            )
        return depth

    @property
    def is_postable(self):
        if not self.pk:
            return True
        return not self.children.exists()

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "An account cannot be its own parent."})
            if self.parent.ledger_id != self.ledger_id:
                raise ValidationError({"parent": "Parent and child must use the same ledger."})
            if AccountClosure.objects.filter(
                ancestor_id=self.pk, descendant_id=self.parent_id
            ).exists():
                raise ValidationError({"parent": "Account hierarchy cannot contain a cycle."})
            if self.parent.account_class != self.account_class:
                raise ValidationError({"account_class": "Child class must match the parent class."})
            if self.parent.normal_balance != self.normal_balance:
                raise ValidationError({"normal_balance": "Child balance side must match the parent."})

    def save(self, *args, **kwargs):
        parent = self.parent if self.parent_id else None
        if parent is not None:
            if not self.ledger_id:
                self.ledger_id = parent.ledger_id
            if not self.account_class:
                self.account_class = parent.account_class
            if not self.normal_balance:
                self.normal_balance = parent.normal_balance
            if parent.ledger_id != self.ledger_id:
                raise ValidationError({"parent": "Parent and child must use the same ledger."})
        if self.level > self.MAX_LEVEL:
            raise ValidationError({"parent": "عمق کدینگ نمی‌تواند از چهار سطح بیشتر باشد."})
        self.path = f"{parent.path}/{self.code}" if parent is not None else self.code
        with transaction.atomic():
            super().save(*args, **kwargs)
            if _defer_closure_rebuild.get() == 0:
                _rebuild_account_closure()

    def __str__(self):
        return self.name


class AccountClosure(models.Model):
    pk = models.CompositePrimaryKey("ancestor", "descendant")
    ancestor = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="descendant_paths")
    descendant = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="ancestor_paths")
    depth = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(depth__gte=0), name="ck_account_depth"),
        ]
        indexes = [models.Index(fields=["descendant", "depth"], name="ix_account_ancestor")]


class TransactionQuerySet(ReferenceQuerySet):
    def update(self, **kwargs):
        if self.filter(status_ref_id=JournalEntry.STATUS_POSTED).exists():
            raise ValidationError("سند ثبت‌شده قابل ویرایش مستقیم نیست. سند اصلاحی صادر کنید.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status_ref_id=JournalEntry.STATUS_POSTED).exists():
            raise ValidationError("سند ثبت‌شده قابل حذف مستقیم نیست. سند اصلاحی صادر کنید.")
        return super().delete()


class TransactionManager(models.Manager.from_queryset(TransactionQuerySet)):
    pass


class JournalLineQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED).exists():
            raise ValidationError("ردیف سند ثبت‌شده قابل ویرایش نیست.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(journal__status_ref_id=JournalEntry.STATUS_POSTED).exists():
            raise ValidationError("ردیف سند ثبت‌شده قابل حذف نیست.")
        return super().delete()


class JournalEntry(ReferenceCodeModel):
    """سرفصل سند دوطرفه.

    نام جدول تاریخی JournalEntry است. در دامنه حسابداری همین رکورد سرفصل است
    و مدل پروکسی Transaction همان سطر را با نام دامنه برمی‌گرداند.
    آرتیکل بدهکار/بستانکار JournalLine است و با کلید خارجی به این سرفصل وصل می‌شود.
    """

    reference_code_fields = {
        "entry_type": "entry_type_ref",
        "status": "status_ref",
    }
    ENTRY_TYPE_CHOICES = [
        ("manual", "دستی"),
        ("sale", "فروش"),
        ("receivable", "دریافتنی"),
        ("payment", "دریافت / پرداخت"),
        ("refund", "برگشت"),
        ("adjustment", "تعدیل"),
        ("other", "سایر"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending_review"
    STATUS_POSTED = "posted"
    STATUS_VOID = "void"
    objects = TransactionManager()
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_PENDING, "در انتظار بررسی"),
        (STATUS_POSTED, "ثبت قطعی"),
        (STATUS_VOID, "باطل"),
    ]
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="journal_entries")
    document_number = models.PositiveBigIntegerField()
    document_code = models.CharField(max_length=40)
    entry_type_ref = models.ForeignKey(
        JournalEntryType, db_column="entry_type", default="manual", on_delete=models.PROTECT
    )
    entry_date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=500, blank=True)
    status_ref = models.ForeignKey(
        JournalEntryStatus, db_column="status", default=STATUS_DRAFT, on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    transfer_source = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transferred_journal",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    override_reason = models.CharField(max_length=500, blank=True, default="")
    overridden_at = models.DateTimeField(null=True, blank=True)
    branch = models.ForeignKey(
        "backend.Branch",
        to_field="code",
        db_column="branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    debit_total = models.DecimalField(default=0, **MONEY_KWARGS)
    credit_total = models.DecimalField(default=0, **MONEY_KWARGS)
    created_at = models.DateTimeField(auto_now_add=True)
    corrects = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )

    class Meta:
        ordering = ["-entry_date", "-document_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["ledger", "document_number"], name="uq_journal_document_number"
            ),
            models.UniqueConstraint(
                fields=["ledger", "document_code"], name="uq_journal_document_code"
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status_ref_id="posted")
                    | models.Q(debit_total=models.F("credit_total"))
                ),
                name="ck_journal_posted_balanced",
            ),
        ]
        indexes = [
            models.Index(fields=["ledger", "status_ref", "entry_date"], name="ix_journal_ledger_date"),
        ]

    entry_type = property(
        lambda self: self.reference_code("entry_type"),
        lambda self, value: self.set_reference_code("entry_type", value),
    )
    status = property(
        lambda self: self.reference_code("status"),
        lambda self, value: self.set_reference_code("status", value),
    )

    def get_entry_type_display(self):
        return self.reference_label("entry_type")

    def get_status_display(self):
        return self.reference_label("status")

    def refresh_totals(self, *, save=False):
        totals = self.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        self.debit_total = totals["debit"] or Decimal("0")
        self.credit_total = totals["credit"] or Decimal("0")
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                debit_total=self.debit_total, credit_total=self.credit_total
            )
        return self

    def save(self, *args, **kwargs):
        if self.pk:
            stored = (
                JournalEntry.objects.filter(pk=self.pk)
                .values_list("status_ref_id", flat=True)
                .first()
            )
            if stored == self.STATUS_POSTED:
                raise ValidationError("سند ثبت‌شده قابل ویرایش مستقیم نیست. سند اصلاحی صادر کنید.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.STATUS_POSTED:
            raise ValidationError("سند ثبت‌شده قابل حذف مستقیم نیست. سند اصلاحی صادر کنید.")
        return super().delete(*args, **kwargs)

    def clean(self):
        if self.status == self.STATUS_POSTED and self.pk:
            self.refresh_totals()
            if self.lines.count() < 2:
                raise ValidationError("Posted journal entries must contain at least two lines.")
            if self.debit_total != self.credit_total:
                raise ValidationError("Posted journal entries must balance.")
            if self.debit_total <= 0:
                raise ValidationError("Posted journal entries must have a positive amount.")

    @transaction.atomic
    def post(self):
        locked = JournalEntry.objects.select_for_update().get(pk=self.pk)
        entry_day = timezone.localdate(locked.entry_date)
        if AccountingPeriod.objects.filter(
            ledger_id=locked.ledger_id,
            status=AccountingPeriod.STATUS_CLOSED,
            date_from__lte=entry_day,
            date_to__gte=entry_day,
        ).exists():
            raise ValidationError("دوره حسابداری این سند بسته است.")
        locked.refresh_totals(save=True)
        locked.status = self.STATUS_POSTED
        locked.posted_at = timezone.now()
        locked.full_clean()
        locked.save(update_fields=["status", "posted_at", "debit_total", "credit_total"])
        self.status = locked.status
        self.posted_at = locked.posted_at
        self.debit_total = locked.debit_total
        self.credit_total = locked.credit_total
        return self

    def attach_origin(self, document, *, module):
        """سرفصل را به UUID یک سند فروش، کارخانه یا انبار وصل می‌کند."""
        origin = AccountingOrigin.register(document, module=module)
        TransactionSource.objects.get_or_create(transaction=self, origin=origin)
        return origin


class Transaction(JournalEntry):
    """سرفصل سند؛ پروکسی روی جدول JournalEntry تا کلیدهای خارجی فعلی نشکند."""

    class Meta:
        proxy = True
        verbose_name = "سرفصل سند"
        verbose_name_plural = "سرفصل‌های سند"


class JournalLine(models.Model):
    """آرتیکل بدهکار یا بستانکار؛ کلید خارجی journal به سرفصل Transaction/JournalEntry."""

    objects = JournalLineQuerySet.as_manager()
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(default=0, **MONEY_KWARGS)
    credit = models.DecimalField(default=0, **MONEY_KWARGS)
    description = models.CharField(max_length=500, blank=True)
    line_number = models.PositiveIntegerField()
    cost_center = models.ForeignKey(
        "backend.CostCenter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )

    class Meta:
        ordering = ["journal", "line_number"]
        constraints = [
            models.UniqueConstraint(fields=["journal", "line_number"], name="uq_journal_line_no"),
            models.CheckConstraint(
                condition=(
                    models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)
                ),
                name="ck_journal_one_side",
            ),
        ]
        indexes = [
            models.Index(fields=["account", "journal"], name="ix_journal_line_account"),
        ]

    @property
    def transaction(self):
        return self.journal

    @transaction.setter
    def transaction(self, value):
        self.journal = value

    def clean(self):
        if self.journal_id and self.account_id:
            if self.journal.ledger_id != self.account.ledger_id:
                raise ValidationError({"account": "Account must belong to the journal ledger."})
            if self.journal.status == JournalEntry.STATUS_POSTED:
                raise ValidationError("Posted journal entries are immutable.")
            if not self.account.is_active:
                raise ValidationError({"account": "حساب غیرفعال قابل ثبت نیست."})
            if not self.account.is_postable:
                raise ValidationError({"account": "فقط حساب تفصیلی (برگ) قابل ثبت است."})
        if self.cost_center_id and self.journal_id:
            if self.cost_center.ledger_id != self.journal.ledger_id:
                raise ValidationError({"cost_center": "Cost center must belong to the journal ledger."})

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        if self.journal_id:
            self.journal.refresh_totals(save=True)
        return result

    def delete(self, *args, **kwargs):
        if self.journal.status == JournalEntry.STATUS_POSTED:
            raise ValidationError("Posted journal entries are immutable.")
        journal = self.journal
        result = super().delete(*args, **kwargs)
        if journal is not None:
            journal.refresh_totals(save=True)
        return result

    @property
    def amount(self):
        return self.debit or self.credit or Decimal("0")

    @property
    def entry_type(self):
        return self.journal.entry_type

    @property
    def entry_date(self):
        return self.journal.entry_date

    @property
    def document_code(self):
        return self.journal.document_code

    @property
    def document_number(self):
        return self.journal.document_number

    @property
    def is_approved(self):
        return self.journal.status == JournalEntry.STATUS_POSTED

    @property
    def sale(self):
        link = self.journal.order_links.select_related("order").filter(
            relation_type="sale"
        ).first()
        return link.order if link else None

    @property
    def sale_id(self):
        link = self.journal.order_links.filter(relation_type="sale").first()
        return link.order_id if link else None

    @property
    def factory_order(self):
        link = self.journal.order_links.select_related("order").filter(
            relation_type="factory_order"
        ).first()
        return link.order.factory_view if link else None

    @property
    def factory_order_id(self):
        link = self.journal.order_links.filter(relation_type="factory_order").first()
        return link.order_id if link else None

    @property
    def created_at(self):
        return self.journal.created_at

    @property
    def transferred_to_office_at(self):
        transferred = getattr(self.journal, "transferred_journal", None)
        return transferred.created_at if transferred else None

    @property
    def office_document_code(self):
        transferred = getattr(self.journal, "transferred_journal", None)
        return transferred.document_code if transferred else ""

    @property
    def attach_code(self):
        source = self.journal.transfer_source
        return source.document_code if source else ""

    def get_entry_type_display(self):
        return self.journal.get_entry_type_display()


class AccountingOrigin(models.Model):
    """لنگر چندریختی با جامعیت InnoDB.

    هر سطر دقیقاً یک سند مبدأ دارد: فاکتور فروش، سفارش تولید کارخانه،
    یا گردش انبار. source_uuid باید همان UUID سطر مبدأ باشد.
    ماژول کارخانه هم می‌تواند به فاکتور (سفارش کارخانه) وصل شود و هم به سفارش تولید.
    """

    MODULE_SALES = "sales"
    MODULE_FACTORY = "factory"
    MODULE_WAREHOUSE = "warehouse"
    MODULE_CHOICES = [
        (MODULE_SALES, "فروش"),
        (MODULE_FACTORY, "کارخانه"),
        (MODULE_WAREHOUSE, "انبار"),
    ]

    module = models.CharField(max_length=16, choices=MODULE_CHOICES)
    source_uuid = models.UUIDField(editable=False)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_origins",
    )
    production_order = models.ForeignKey(
        "backend.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_origins",
    )
    inventory_transaction = models.ForeignKey(
        "backend.InventoryTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_origins",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["module", "source_uuid"], name="uq_origin_module_uuid"),
            models.UniqueConstraint(fields=["module", "sale"], name="uq_origin_module_sale"),
            models.UniqueConstraint(fields=["production_order"], name="uq_origin_production"),
            models.UniqueConstraint(fields=["inventory_transaction"], name="uq_origin_inventory"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        module="sales",
                        sale__isnull=False,
                        production_order__isnull=True,
                        inventory_transaction__isnull=True,
                    )
                    | models.Q(
                        module="factory",
                        sale__isnull=False,
                        production_order__isnull=True,
                        inventory_transaction__isnull=True,
                    )
                    | models.Q(
                        module="factory",
                        production_order__isnull=False,
                        sale__isnull=True,
                        inventory_transaction__isnull=True,
                    )
                    | models.Q(
                        module="warehouse",
                        inventory_transaction__isnull=False,
                        sale__isnull=True,
                        production_order__isnull=True,
                    )
                ),
                name="ck_origin_arc",
            ),
        ]

    def __str__(self):
        return f"{self.module}:{self.source_uuid}"

    def _bound_document(self):
        sale_set = bool(self.sale_id)
        production_set = bool(self.production_order_id)
        inventory_set = bool(self.inventory_transaction_id)
        if self.module == self.MODULE_SALES and sale_set and not production_set and not inventory_set:
            return self.sale
        if (
            self.module == self.MODULE_FACTORY
            and production_set
            and not sale_set
            and not inventory_set
        ):
            return self.production_order
        if self.module == self.MODULE_FACTORY and sale_set and not production_set and not inventory_set:
            return self.sale
        if (
            self.module == self.MODULE_WAREHOUSE
            and inventory_set
            and not sale_set
            and not production_set
        ):
            return self.inventory_transaction
        raise ValidationError(
            "مبدأ سند باید دقیقاً یکی از فروش، کارخانه یا انبار باشد و با ماژول هم‌خوان باشد."
        )

    def resolve(self):
        return self._bound_document()

    def clean(self):
        self.source_uuid = self._bound_document().uuid

    def save(self, *args, **kwargs):
        self.source_uuid = self._bound_document().uuid
        self.full_clean()
        return super().save(*args, **kwargs)

    @classmethod
    def register(cls, document, *, module):
        from backend.models.catalog import InventoryTransaction
        from backend.models.office_forms import ProductionOrder
        from backend.models.orders import Sale

        if module == cls.MODULE_WAREHOUSE:
            if not isinstance(document, InventoryTransaction):
                raise ValidationError("مبدأ انبار باید یک گردش موجودی باشد.")
            lookup = {"module": module, "inventory_transaction": document}
        elif module == cls.MODULE_SALES:
            if not isinstance(document, Sale):
                raise ValidationError("مبدأ فروش باید یک فاکتور فروش باشد.")
            lookup = {"module": module, "sale": document}
        elif module == cls.MODULE_FACTORY:
            if isinstance(document, ProductionOrder):
                lookup = {"module": module, "production_order": document}
            elif isinstance(document, Sale):
                lookup = {"module": module, "sale": document}
            else:
                raise ValidationError("مبدأ کارخانه باید سفارش تولید یا فاکتور کارخانه باشد.")
        else:
            raise ValidationError("ماژول مبدأ نامعتبر است.")
        origin, _created = cls.objects.get_or_create(
            **lookup,
            defaults={"source_uuid": document.uuid},
        )
        return origin


class TransactionSource(models.Model):
    """اتصال سرفصل سند به لنگر UUID. حذف سند مبدأ تا وقتی لینک هست ممنوع است."""

    transaction = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="sources"
    )
    origin = models.ForeignKey(
        AccountingOrigin, on_delete=models.PROTECT, related_name="transaction_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["transaction", "origin"], name="uq_tx_source"),
        ]

    def __str__(self):
        return f"{self.transaction_id} → {self.origin_id}"


class JournalOrderLink(models.Model):
    pk = models.CompositePrimaryKey("journal", "order", "relation_type")
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="order_links")
    order = models.ForeignKey(
        "backend.Sale", on_delete=models.PROTECT, related_name="journal_links"
    )
    relation_type = models.CharField(max_length=30, default="source")


class UserAccountingPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounting_preference"
    )
    default_check_registration_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_for_check_registration",
    )
    default_check_deposit_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_for_check_deposit",
    )
    updated_at = models.DateTimeField(auto_now=True)


class SubsidiaryAccount(Account):
    class Meta:
        proxy = True

    @property
    def account(self):
        return self.parent

    @account.setter
    def account(self, value):
        self.parent = value


class DetailedAccount(Account):
    class Meta:
        proxy = True

    @property
    def subsidiary(self):
        return self.parent

    @subsidiary.setter
    def subsidiary(self, value):
        self.parent = value


class FactoryAccountManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ledger__kind=Ledger.KIND_FACTORY)


class FactoryAccount(Account):
    objects = FactoryAccountManager()

    class Meta:
        proxy = True


class FactorySubsidiaryAccount(SubsidiaryAccount):
    objects = FactoryAccountManager()

    class Meta:
        proxy = True


class FactoryDetailedAccount(DetailedAccount):
    objects = FactoryAccountManager()

    class Meta:
        proxy = True


class LegacyAccountingEntryQuerySet(models.QuerySet):
    """Translate the former single-row query API onto normalized journal lines."""

    LOOKUP_MAP = {
        "entry_type": "journal__entry_type_ref_id",
        "sale": "journal__order_links__order",
        "sale_id": "journal__order_links__order_id",
        "factory_order": "journal__order_links__order",
        "factory_order_id": "journal__order_links__order_id",
        "is_approved": "journal__status_ref_id",
        "document_code": "journal__document_code",
        "document_number": "journal__document_number",
        "entry_date": "journal__entry_date",
        "created_at": "journal__created_at",
    }

    @classmethod
    def _translate_kwargs(cls, kwargs):
        translated = {}
        for key, value in kwargs.items():
            root, separator, lookup = key.partition("__")
            mapped = cls.LOOKUP_MAP.get(root, root)
            if root == "is_approved":
                value = JournalEntry.STATUS_POSTED if value else JournalEntry.STATUS_DRAFT
            translated[mapped + (separator + lookup if separator else "")] = value
        return translated

    def _filter_or_exclude(self, negate, args, kwargs):
        return super()._filter_or_exclude(negate, args, self._translate_kwargs(kwargs))


class LegacyAccountingEntryManager(models.Manager.from_queryset(LegacyAccountingEntryQuerySet)):
    def get_queryset(self):
        return super().get_queryset().exclude(
            journal__status_ref_id=JournalEntry.STATUS_VOID
        )

    def create(self, **kwargs):
        from logic.accounting import create_accounting_entry

        kwargs.setdefault("is_approved", False)
        return create_accounting_entry(**kwargs)


class AccountingEntry(JournalLine):
    ENTRY_TYPE_CHOICES = JournalEntry.ENTRY_TYPE_CHOICES
    objects = LegacyAccountingEntryManager()

    class Meta:
        proxy = True


class FactoryAccountingEntry(AccountingEntry):
    class Meta:
        proxy = True


class JournalRevision(models.Model):
    ACTION_SUBMIT = "submit"
    ACTION_OVERRIDE = "override"
    ACTION_POST = "post"
    ACTION_UNPOST = "unpost"
    ACTION_VOID = "void"
    ACTION_CORRECT = "correct"
    ACTION_CHOICES = [
        (ACTION_SUBMIT, "ارسال برای بررسی"),
        (ACTION_OVERRIDE, "ویرایش انسانی"),
        (ACTION_POST, "ثبت قطعی"),
        (ACTION_UNPOST, "برگشت از ثبت"),
        (ACTION_VOID, "ابطال"),
        (ACTION_CORRECT, "سند اصلاحی"),
    ]
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="revisions")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.CharField(max_length=500, blank=True, default="")
    before_lines = models.JSONField(default=list, blank=True)
    after_lines = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class FinancialEvent(models.Model):
    """رویداد مالی idempotent که یک عملیات واقعی را به سند متصل می‌کند."""

    STATUS_PENDING = "pending"
    STATUS_DRAFTED = "drafted"
    STATUS_POSTED = "posted"
    STATUS_FAILED = "failed"
    STATUS_VOID = "void"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار صدور"),
        (STATUS_DRAFTED, "پیش‌نویس صادر شد"),
        (STATUS_POSTED, "ثبت قطعی شد"),
        (STATUS_FAILED, "خطا"),
        (STATUS_VOID, "باطل"),
    ]

    source_module = models.CharField(max_length=40)
    source_type = models.CharField(max_length=80)
    source_key = models.CharField(max_length=120)
    event_type = models.CharField(max_length=60)
    rule_version = models.CharField(max_length=20, default="1")
    payload = models.JSONField(default=dict, blank=True)
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    journal = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="financial_events",
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_module", "source_type", "source_key", "event_type"],
                name="uq_financial_event_source",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "occurred_at"], name="ix_fin_event_status"),
            models.Index(fields=["source_module", "source_type"], name="ix_fin_event_source"),
        ]

    def __str__(self):
        return f"{self.source_module}:{self.source_type}:{self.source_key}:{self.event_type}"


class AccountingPeriod(models.Model):
    """قفل دوره حسابداری؛ ثبت قطعی در دوره بسته ممنوع است."""

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_REOPENED = "reopened"
    STATUS_CHOICES = [
        (STATUS_OPEN, "باز"),
        (STATUS_CLOSED, "بسته"),
        (STATUS_REOPENED, "بازگشایی‌شده"),
    ]

    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="periods")
    date_from = models.DateField()
    date_to = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_accounting_periods",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["ledger", "date_from", "date_to"], name="uq_accounting_period"
            ),
            models.CheckConstraint(
                condition=models.Q(date_to__gte=models.F("date_from")),
                name="ck_accounting_period_dates",
            ),
        ]

    def __str__(self):
        return f"{self.ledger.code}:{self.date_from}..{self.date_to}"


class LedgerMigrationAudit(models.Model):
    """ردپای قابل rollback برای ادغام دفتر کارخانه در دفتر قانونی."""

    batch_id = models.UUIDField()
    action = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=120)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["batch_id", "id"]
        indexes = [
            models.Index(fields=["batch_id", "action"], name="ix_ledger_migration"),
        ]

    def __str__(self):
        return f"{self.batch_id}:{self.action}:{self.entity_type}:{self.entity_id}"


class CostCenter(models.Model):
    KIND_PRODUCTION = "production"
    KIND_SHOWROOM = "showroom"
    KIND_ADMIN = "admin"
    KIND_CHOICES = [
        (KIND_PRODUCTION, "تولید"),
        (KIND_SHOWROOM, "شوروم"),
        (KIND_ADMIN, "اداری"),
    ]
    BASE_MACHINE_HOURS = "machine_hours"
    BASE_FLOOR_AREA = "floor_area"
    BASE_LABOR_HOURS = "labor_hours"
    BASE_DIRECT_COST = "direct_cost"
    BASE_CHOICES = [
        (BASE_MACHINE_HOURS, "ساعات ماشین"),
        (BASE_FLOOR_AREA, "متراژ"),
        (BASE_LABOR_HOURS, "ساعات کار"),
        (BASE_DIRECT_COST, "بهای مستقیم"),
    ]
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="cost_centers")
    branch = models.ForeignKey(
        "backend.Branch",
        to_field="code",
        db_column="branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centers",
    )
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_PRODUCTION)
    allocation_base = models.CharField(max_length=20, choices=BASE_CHOICES, default=BASE_MACHINE_HOURS)
    base_quantity = models.DecimalField(default=0, max_digits=18, decimal_places=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["ledger", "code"], name="uq_cost_center_ledger_code"),
            models.CheckConstraint(condition=models.Q(base_quantity__gte=0), name="ck_cost_center_base"),
        ]

    def __str__(self):
        return self.name


class OverheadPeriod(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ALLOCATED = "allocated"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_ALLOCATED, "تسهیم‌شده"),
    ]
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="overhead_periods")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(default=0, **MONEY_KWARGS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    journal = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="overhead_periods"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["ledger", "year", "month"], name="uq_overhead_period"),
            models.CheckConstraint(condition=models.Q(month__gte=1, month__lte=12), name="ck_overhead_month"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="ck_overhead_amount"),
        ]


class OverheadAllocationLine(models.Model):
    period = models.ForeignKey(OverheadPeriod, on_delete=models.CASCADE, related_name="lines")
    cost_center = models.ForeignKey(CostCenter, on_delete=models.PROTECT, related_name="allocation_lines")
    base_quantity = models.DecimalField(default=0, max_digits=18, decimal_places=3)
    share_amount = models.DecimalField(default=0, **MONEY_KWARGS)

    class Meta:
        ordering = ["cost_center_id"]
        constraints = [
            models.UniqueConstraint(fields=["period", "cost_center"], name="uq_overhead_center"),
        ]


class WipClose(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="wip_closes")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    product = models.ForeignKey(
        "backend.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="wip_closes"
    )
    recipe = models.ForeignKey(
        "backend.WorkshopRecipe", null=True, blank=True, on_delete=models.PROTECT, related_name="wip_closes"
    )
    completed_units = models.DecimalField(default=0, max_digits=18, decimal_places=3)
    ending_wip_units = models.DecimalField(default=0, max_digits=18, decimal_places=3)
    percent_complete = models.DecimalField(default=0, max_digits=6, decimal_places=2)
    equivalent_units = models.DecimalField(default=0, max_digits=18, decimal_places=3)
    material_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    labor_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    overhead_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    journal = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="wip_closes",
    )
    notes = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(month__gte=1, month__lte=12), name="ck_wip_month"),
            models.CheckConstraint(condition=models.Q(completed_units__gte=0), name="ck_wip_completed"),
            models.CheckConstraint(condition=models.Q(ending_wip_units__gte=0), name="ck_wip_ending"),
            models.CheckConstraint(
                condition=models.Q(percent_complete__gte=0, percent_complete__lte=100),
                name="ck_wip_percent",
            ),
            models.CheckConstraint(condition=models.Q(material_cost__gte=0), name="ck_wip_material_cost"),
            models.CheckConstraint(condition=models.Q(labor_cost__gte=0), name="ck_wip_labor_cost"),
            models.CheckConstraint(condition=models.Q(overhead_cost__gte=0), name="ck_wip_overhead_cost"),
        ]

    def save(self, *args, **kwargs):
        rate = Decimal(self.percent_complete or 0) / Decimal(100)
        units = Decimal(self.completed_units or 0) + Decimal(self.ending_wip_units or 0) * rate
        self.equivalent_units = units.quantize(Decimal("0.001"))
        return super().save(*args, **kwargs)


class UnidentifiedDeposit(models.Model):
    STATUS_OPEN = "open"
    STATUS_ALLOCATED = "allocated"
    STATUS_CHOICES = [
        (STATUS_OPEN, "باز"),
        (STATUS_ALLOCATED, "تخصیص‌شده"),
    ]
    deposit_date = models.DateField()
    amount = models.DecimalField(**MONEY_KWARGS)
    bank_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="unidentified_deposits")
    description = models.CharField(max_length=300, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    customer = models.ForeignKey(
        "backend.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="unidentified_deposits"
    )
    journal = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="unidentified_deposits"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deposit_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_unidentified_amount"),
        ]


class TradeDocument(models.Model):
    """سند مثبته خرید و فروش — سیستم دائمی، روش ناخالص تخفیف نقدی."""

    KIND_PURCHASE = "purchase"
    KIND_PURCHASE_RETURN = "purchase_return"
    KIND_SALE = "sale"
    KIND_SALE_RETURN = "sale_return"
    KIND_PURCHASE_DISCOUNT = "purchase_discount"
    KIND_SALE_DISCOUNT = "sale_discount"
    KIND_CHOICES = [
        (KIND_PURCHASE, "خرید"),
        (KIND_PURCHASE_RETURN, "برگشت از خرید"),
        (KIND_SALE, "فروش"),
        (KIND_SALE_RETURN, "برگشت از فروش"),
        (KIND_PURCHASE_DISCOUNT, "تخفیف نقدی خرید"),
        (KIND_SALE_DISCOUNT, "تخفیف نقدی فروش"),
    ]
    SETTLEMENT_CASH = "cash"
    SETTLEMENT_CREDIT = "credit"
    SETTLEMENT_CHOICES = [
        (SETTLEMENT_CASH, "نقد"),
        (SETTLEMENT_CREDIT, "نسیه"),
    ]

    material = models.ForeignKey(
        "backend.Material", on_delete=models.PROTECT, related_name="trade_documents"
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    settlement = models.CharField(max_length=10, choices=SETTLEMENT_CHOICES, default=SETTLEMENT_CREDIT)
    quantity = models.DecimalField(default=0, **QUANTITY_KWARGS)
    remaining_qty = models.DecimalField(default=0, **QUANTITY_KWARGS)
    unit_price = models.DecimalField(default=0, **MONEY_KWARGS)
    trade_discount = models.DecimalField(default=0, **MONEY_KWARGS)
    freight = models.DecimalField(default=0, **MONEY_KWARGS)
    insurance = models.DecimalField(default=0, **MONEY_KWARGS)
    other_cost = models.DecimalField(default=0, **MONEY_KWARGS)
    goods_net = models.DecimalField(default=0, **MONEY_KWARGS)
    charges = models.DecimalField(default=0, **MONEY_KWARGS)
    inventory_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    vat_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    cogs_amount = models.DecimalField(default=0, **MONEY_KWARGS)
    cash_discount = models.DecimalField(default=0, **MONEY_KWARGS)
    invoice_number = models.CharField(max_length=60, blank=True)
    warehouse_receipt = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=300, blank=True)
    journal = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="trade_documents"
    )
    inventory_move = models.ForeignKey(
        "backend.InventoryTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="trade_documents",
    )
    source = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="adjustments"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_trade_qty"),
            models.CheckConstraint(condition=models.Q(remaining_qty__gte=0), name="ck_trade_remaining"),
            models.CheckConstraint(condition=models.Q(vat_rate__gte=0), name="ck_trade_vat_rate"),
        ]


def _rebuild_account_closure():
    parents = dict(Account.objects.values_list("id", "parent_id"))
    paths = []
    for descendant_id in parents:
        seen = {descendant_id}
        ancestor_id = descendant_id
        depth = 0
        while ancestor_id is not None:
            paths.append(
                AccountClosure(
                    ancestor_id=ancestor_id,
                    descendant_id=descendant_id,
                    depth=depth,
                )
            )
            ancestor_id = parents.get(ancestor_id)
            depth += 1
            if ancestor_id in seen:
                raise ValidationError("Account hierarchy cannot contain a cycle.")
            seen.add(ancestor_id)
    with transaction.atomic():
        AccountClosure.objects.all().delete()
        AccountClosure.objects.bulk_create(paths, batch_size=1000)
