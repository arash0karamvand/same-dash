"""Unified ledgers, hierarchical accounts, and double-entry journals."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from .base import MONEY_KWARGS, ReferenceCodeModel
from .config import JournalEntryStatus, JournalEntryType


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
    CLASS_CHOICES = [
        ("asset", "دارایی"),
        ("liability", "بدهی"),
        ("equity", "سرمایه"),
        ("revenue", "درآمد"),
        ("expense", "هزینه"),
    ]
    NORMAL_BALANCE_CHOICES = [("debit", "بدهکار"), ("credit", "بستانکار")]
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
            models.UniqueConstraint(
                fields=["ledger", "path"],
                name="uq_account_ledger_path",
            ),
            models.CheckConstraint(condition=~models.Q(code=""), name="ck_account_code_nonempty"),
        ]
        indexes = [models.Index(fields=["ledger", "parent", "sort_order"], name="ix_account_tree")]

    @property
    def full_code(self):
        return self.path

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

    def save(self, *args, **kwargs):
        if self.parent_id and not self.ledger_id:
            self.ledger_id = self.parent.ledger_id
        if self.parent_id and self.parent.ledger_id != self.ledger_id:
            raise ValidationError({"parent": "Parent and child must use the same ledger."})
        self.path = f"{self.parent.path}/{self.code}" if self.parent_id else self.code
        with transaction.atomic():
            super().save(*args, **kwargs)
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


class JournalEntry(ReferenceCodeModel):
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
    STATUS_POSTED = "posted"
    STATUS_VOID = "void"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_date", "-document_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["ledger", "document_number"], name="uq_journal_document_number"
            ),
            models.UniqueConstraint(
                fields=["ledger", "document_code"], name="uq_journal_document_code"
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

    def clean(self):
        if self.status == self.STATUS_POSTED and self.pk:
            totals = self.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
            if self.lines.count() < 2:
                raise ValidationError("Posted journal entries must contain at least two lines.")
            if (totals["debit"] or 0) != (totals["credit"] or 0):
                raise ValidationError("Posted journal entries must balance.")

    @transaction.atomic
    def post(self):
        locked = JournalEntry.objects.select_for_update().get(pk=self.pk)
        locked.status = self.STATUS_POSTED
        locked.posted_at = timezone.now()
        locked.full_clean()
        locked.save(update_fields=["status", "posted_at"])
        self.status = locked.status
        self.posted_at = locked.posted_at
        return self


class JournalLine(models.Model):
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(default=0, **MONEY_KWARGS)
    credit = models.DecimalField(default=0, **MONEY_KWARGS)
    description = models.CharField(max_length=500, blank=True)
    line_number = models.PositiveIntegerField()

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

    def clean(self):
        if self.journal_id and self.account_id:
            if self.journal.ledger_id != self.account.ledger_id:
                raise ValidationError({"account": "Account must belong to the journal ledger."})
            if self.journal.status == JournalEntry.STATUS_POSTED:
                raise ValidationError("Posted journal entries are immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.journal.status == JournalEntry.STATUS_POSTED:
            raise ValidationError("Posted journal entries are immutable.")
        return super().delete(*args, **kwargs)

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
    AccountClosure.objects.all().delete()
    AccountClosure.objects.bulk_create(paths)
