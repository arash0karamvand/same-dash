"""مدل‌های دامنه پروژه."""

from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone

from backend.soft_delete import SoftDeleteModel

MONEY_KWARGS = {"max_digits": 18, "decimal_places": 0}

BRANCH_CHOICES = [
    ("branch_1", "کمرد"),
    ("branch_2", "پاسداران"),
]


class LoyaltyLevel(SoftDeleteModel):
    name = models.CharField("نام سطح", max_length=50, unique=True)
    min_purchase = models.DecimalField("حداقل خرید", default=0, **MONEY_KWARGS)
    max_purchase = models.DecimalField("حداکثر خرید", null=True, blank=True, **MONEY_KWARGS)
    discount_percent = models.DecimalField("درصد تخفیف", max_digits=5, decimal_places=2, default=0)
    points = models.IntegerField("امتیاز سطح", default=0)
    description = models.TextField("توضیحات", blank=True)
    color = models.CharField("رنگ نمایشی", max_length=20, default="#6366f1")
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "سطح باشگاه"
        verbose_name_plural = "سطوح باشگاه"
        ordering = ["min_purchase"]

    def __str__(self):
        return self.name


class Customer(SoftDeleteModel):
    full_name = models.CharField("نام کامل", max_length=150)
    phone = models.CharField("موبایل", max_length=20, unique=True)
    membership_code = models.CharField(
        "کد عضویت باشگاه",
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    email = models.EmailField("ایمیل", blank=True)
    joined_at = models.DateTimeField("تاریخ عضویت", auto_now_add=True)
    is_active = models.BooleanField("فعال", default=True)
    notes = models.TextField("توضیحات داخلی", blank=True)
    birthday = models.DateField("تاریخ تولد", null=True, blank=True)
    wallet_balance = models.DecimalField("موجودی کیف پول", default=0, **MONEY_KWARGS)
    total_purchases = models.DecimalField("مجموع کل خرید", default=0, **MONEY_KWARGS)
    last_purchase_at = models.DateTimeField("آخرین تاریخ خرید", null=True, blank=True)
    level = models.ForeignKey(
        LoyaltyLevel,
        verbose_name="سطح فعلی",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customers",
    )
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "مشتری"
        verbose_name_plural = "مشتریان"
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class OrgRank(models.Model):
    """رتبه سازمانی قابل تعریف توسط مدیر — مثلاً سرپرست شعبه."""

    name = models.CharField("عنوان رتبه", max_length=80)
    branch = models.CharField("شعبه", max_length=20, choices=BRANCH_CHOICES, blank=True)
    color = models.CharField("رنگ", max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "رتبه سازمانی"
        verbose_name_plural = "رتبه‌های سازمانی"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class RoleDefinition(models.Model):
    """نقش و مجوزهای قابل تنظیم توسط مدیر سیستم."""

    slug = models.SlugField("شناسه", max_length=40, unique=True)
    label = models.CharField("عنوان", max_length=80)
    description = models.TextField("توضیحات", blank=True)
    permissions = models.JSONField("مجوزها", default=list)
    is_builtin = models.BooleanField("نقش پیش‌فرض", default=False)
    needs_branch = models.BooleanField("نیاز به شعبه", default=False)
    color = models.CharField("رنگ", max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    parent = models.ForeignKey(
        "self",
        verbose_name="نقش والد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    class Meta:
        verbose_name = "تعریف نقش"
        verbose_name_plural = "تعریف نقش‌ها"
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class StaffProfile(models.Model):
    """پروفایل پرسنل فروش — شعبه و سلسله‌مراتب."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    branch = models.CharField("شعبه", max_length=20, choices=BRANCH_CHOICES, default="branch_1")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="مدیر مستقیم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
    )
    job_title = models.CharField("عنوان شغلی", max_length=100, blank=True)
    org_rank = models.ForeignKey(
        OrgRank,
        verbose_name="رتبه سازمانی",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_members",
    )

    class Meta:
        verbose_name = "پروفایل پرسنل"
        verbose_name_plural = "پروفایل پرسنل"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_branch_display()}"


class Sale(SoftDeleteModel):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "نقدی"),
        ("card", "کارت‌خوان"),
        ("online", "آنلاین"),
        ("credit", "اعتباری"),
        ("check", "چک"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("paid", "پرداخت‌شده"),
        ("unpaid", "پرداخت‌نشده"),
        ("installment", "قسطی"),
    ]

    customer = models.ForeignKey(
        Customer, verbose_name="مشتری", on_delete=models.CASCADE, related_name="sales"
    )
    DISCOUNT_TYPE_CHOICES = [
        ("percent", "درصدی"),
        ("amount", "مبلغ ثابت"),
        ("wallet", "موجودی حساب"),
    ]

    amount = models.DecimalField("مبلغ فروش", **MONEY_KWARGS)
    discount_type = models.CharField(
        "نوع تخفیف", max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="amount"
    )
    discount_value = models.DecimalField("مقدار تخفیف (ورودی)", default=0, **MONEY_KWARGS)
    discount = models.DecimalField("تخفیف (تومان)", default=0, **MONEY_KWARGS)
    final_amount = models.DecimalField("مبلغ نهایی", default=0, **MONEY_KWARGS)
    paid_amount = models.DecimalField("مبلغ پرداخت‌شده", default=0, **MONEY_KWARGS)
    sold_at = models.DateTimeField("تاریخ فروش", default=timezone.now)
    invoice_number = models.CharField("شماره فاکتور", max_length=40, blank=True)
    description = models.CharField("توضیحات", max_length=255, blank=True)
    payment_status = models.CharField(
        "وضعیت پرداخت", max_length=12, choices=PAYMENT_STATUS_CHOICES, default="paid"
    )
    payment_method = models.CharField(
        "روش پرداخت", max_length=10, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_sales",
    )
    branch = models.CharField("شعبه", max_length=20, choices=BRANCH_CHOICES, blank=True)
    seller = models.ForeignKey(
        "Seller",
        verbose_name="فروشنده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "فروش"
        verbose_name_plural = "فروش‌ها"
        ordering = ["-sold_at"]

    def __str__(self):
        return f"فاکتور {self.invoice_number or self.pk} - {self.final_amount}"


class SaleInstallment(SoftDeleteModel):
    """قسط یا چک مرتبط با فروش."""

    STATUS_CHOICES = [
        ("pending", "در انتظار"),
        ("paid", "پرداخت‌شده"),
        ("cancelled", "لغوشده"),
    ]
    PAYMENT_METHOD_CHOICES = Sale.PAYMENT_METHOD_CHOICES

    sale = models.ForeignKey(
        Sale, verbose_name="فروش", on_delete=models.CASCADE, related_name="installments"
    )
    amount = models.DecimalField("مبلغ قسط", **MONEY_KWARGS)
    due_date = models.DateField("تاریخ سررسید")
    payment_method = models.CharField(
        "روش پرداخت", max_length=10, choices=PAYMENT_METHOD_CHOICES, default="cash"
    )
    check_number = models.CharField("شماره چک", max_length=50, blank=True)
    bank_name = models.CharField("نام بانک", max_length=100, blank=True)
    status = models.CharField("وضعیت", max_length=12, choices=STATUS_CHOICES, default="pending")
    paid_at = models.DateTimeField("تاریخ پرداخت", null=True, blank=True)
    notes = models.CharField("توضیحات", max_length=255, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "قسط فروش"
        verbose_name_plural = "اقساط فروش"
        ordering = ["due_date"]

    def __str__(self):
        return f"قسط {self.amount} — {self.due_date}"


class Seller(SoftDeleteModel):
    """فروشنده — بدون نیاز به نام کاربری؛ اتصال اختیاری به حساب ورود."""

    full_name = models.CharField("نام کامل", max_length=150)
    branch = models.CharField("شعبه", max_length=20, choices=BRANCH_CHOICES, default="branch_1")
    phone = models.CharField("موبایل", max_length=20, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب ورود",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seller_profile",
    )
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "فروشنده"
        verbose_name_plural = "فروشندگان"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class ProductCategory(SoftDeleteModel):
    """دسته‌بندی محصولات."""

    name = models.CharField("نام دسته", max_length=100, unique=True)
    description = models.TextField("توضیحات", blank=True)
    color = models.CharField("رنگ نمایش", max_length=7, default="#6366f1")
    icon = models.CharField("آیکون", max_length=8, blank=True, default="📦")
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "دسته محصول"
        verbose_name_plural = "دسته‌های محصول"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Product(SoftDeleteModel):
    category = models.ForeignKey(
        ProductCategory,
        verbose_name="دسته",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    name = models.CharField("نام محصول", max_length=150)
    sku = models.CharField("کد محصول", max_length=50, blank=True, db_index=True)
    brand = models.CharField("برند", max_length=100, blank=True)
    description = models.TextField("توضیحات", blank=True)
    unit = models.CharField("واحد", max_length=20, default="عدد")
    attributes = models.JSONField("ویژگی‌های سفارشی", default=dict, blank=True)
    default_price = models.DecimalField("قیمت پیش‌فرض", default=0, **MONEY_KWARGS)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def display_price(self):
        active = self.variants.filter(is_active=True).order_by("sort_order", "id").first()
        if active:
            return active.price
        return self.default_price


class ProductVariant(models.Model):
    """رنگ/تنوع محصول — هر محصول می‌تواند چند رنگبندی داشته باشد."""

    product = models.ForeignKey(
        Product,
        verbose_name="محصول",
        on_delete=models.CASCADE,
        related_name="variants",
    )
    color_name = models.CharField("نام رنگ", max_length=50)
    color_hex = models.CharField("کد رنگ", max_length=7, default="#cccccc")
    sku = models.CharField("کد تنوع", max_length=60, blank=True)
    price = models.DecimalField("قیمت", default=0, **MONEY_KWARGS)
    stock = models.PositiveIntegerField("موجودی", null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "تنوع محصول"
        verbose_name_plural = "تنوع‌های محصول"
        ordering = ["sort_order", "id"]
        unique_together = [("product", "color_name")]

    def __str__(self):
        return f"{self.product.name} — {self.color_name}"


class SaleLineItem(models.Model):
    sale = models.ForeignKey(Sale, verbose_name="فروش", on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(
        Product, verbose_name="محصول", null=True, blank=True, on_delete=models.SET_NULL, related_name="sale_lines"
    )
    variant = models.ForeignKey(
        ProductVariant,
        verbose_name="تنوع",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sale_lines",
    )
    product_name = models.CharField("نام محصول", max_length=150)
    color_name = models.CharField("رنگ", max_length=50, blank=True)
    color_hex = models.CharField("کد رنگ", max_length=7, blank=True)
    quantity = models.PositiveIntegerField("تعداد", default=1)
    unit_price = models.DecimalField("قیمت واحد", **MONEY_KWARGS)
    line_total = models.DecimalField("جمع ردیف", **MONEY_KWARGS)

    class Meta:
        verbose_name = "ردیف فروش"
        verbose_name_plural = "ردیف‌های فروش"

    def __str__(self):
        label = self.product_name
        if self.color_name:
            label = f"{label} ({self.color_name})"
        return f"{label} x{self.quantity}"


class StaffAttendance(SoftDeleteModel):
    """حضور و غیاب فروشندگان."""

    STATUS_CHOICES = [
        ("present", "حاضر"),
        ("absent", "غایب"),
    ]

    APPROVAL_CHOICES = [
        ("pending", "در انتظار تایید"),
        ("approved", "تایید شده"),
        ("rejected", "رد شده"),
    ]

    seller = models.ForeignKey(
        Seller,
        verbose_name="فروشنده",
        on_delete=models.CASCADE,
        related_name="attendance",
    )
    date = models.DateField("تاریخ")
    status = models.CharField("وضعیت", max_length=10, choices=STATUS_CHOICES, default="present")
    work_branch = models.CharField(
        "شعبه کاری", max_length=20, choices=BRANCH_CHOICES, blank=True,
    )
    approval_status = models.CharField(
        "وضعیت تایید", max_length=12, choices=APPROVAL_CHOICES, default="approved"
    )
    notes = models.CharField("توضیحات", max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_attendance",
    )
    approved_at = models.DateTimeField("تاریخ تایید", null=True, blank=True)
    check_in_at = models.DateTimeField("زمان ورود", null=True, blank=True)
    check_out_at = models.DateTimeField("زمان پایان کار", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "حضور و غیاب فروشنده"
        verbose_name_plural = "حضور و غیاب فروشندگان"
        ordering = ["-date"]
        unique_together = [("seller", "date")]

    def __str__(self):
        return f"{self.seller.full_name} — {self.date}"


# سازگاری با importهای قدیمی
CustomerAttendance = StaffAttendance


class AccountingEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("sale", "فروش"),
        ("receivable", "مطالبات (بدهکار مشتری)"),
        ("payment", "دریافت قسط/پرداخت"),
        ("refund", "مرجوعی"),
        ("adjustment", "اصلاح"),
        ("other", "سایر"),
    ]

    entry_type = models.CharField(
        "نوع سند", max_length=20, choices=ENTRY_TYPE_CHOICES, default="sale"
    )
    debit = models.DecimalField("بدهکار", default=0, **MONEY_KWARGS)
    credit = models.DecimalField("بستانکار", default=0, **MONEY_KWARGS)
    amount = models.DecimalField("مبلغ", default=0, **MONEY_KWARGS)
    entry_date = models.DateTimeField("تاریخ سند", default=timezone.now)
    description = models.CharField("توضیحات", max_length=255, blank=True)
    sale = models.ForeignKey(
        Sale,
        verbose_name="فروش مرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_entries",
    )
    is_approved = models.BooleanField("تایید حسابداری", default=False)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "سند حسابداری"
        verbose_name_plural = "اسناد حسابداری"
        ordering = ["-entry_date"]

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.amount}"


class CustomerLevelHistory(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name="مشتری", on_delete=models.CASCADE, related_name="level_history"
    )
    previous_level = models.ForeignKey(
        LoyaltyLevel, verbose_name="سطح قبلی", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    new_level = models.ForeignKey(
        LoyaltyLevel, verbose_name="سطح جدید", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    changed_at = models.DateTimeField("تاریخ تغییر", auto_now_add=True)
    reason = models.CharField("دلیل تغییر", max_length=255, blank=True)
    total_purchases_at_change = models.DecimalField(
        "مجموع خرید در زمان تغییر", default=0, **MONEY_KWARGS
    )

    class Meta:
        verbose_name = "تاریخچه سطح مشتری"
        verbose_name_plural = "تاریخچه سطوح مشتریان"
        ordering = ["-changed_at"]

    def __str__(self):
        prev = self.previous_level.name if self.previous_level else "—"
        new = self.new_level.name if self.new_level else "—"
        return f"{self.customer.full_name}: {prev} → {new}"


class SMSLog(models.Model):
    STATUS_CHOICES = [
        ("pending", "در صف"),
        ("sent", "ارسال شد"),
        ("failed", "ناموفق"),
        ("mock_sent", "شبیه‌سازی"),
        ("pending_provider_config", "در انتظار تنظیم درگاه"),
    ]
    TYPE_CHOICES = [
        ("manual", "دستی"),
        ("welcome", "خوش‌آمدگویی"),
        ("level_up", "ارتقای سطح"),
        ("promotion", "تبلیغاتی"),
        ("birthday", "تبریک تولد"),
        ("order_placed", "ثبت سفارش"),
        ("discount", "تخفیف ویژه"),
        ("reminder", "یادآوری باشگاه"),
    ]

    customer = models.ForeignKey(
        Customer, verbose_name="مشتری", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sms_logs",
    )
    phone_number = models.CharField("شماره موبایل", max_length=20)
    message = models.TextField("متن پیام")
    sms_type = models.CharField("نوع پیامک", max_length=20, choices=TYPE_CHOICES, default="manual")
    status = models.CharField("وضعیت", max_length=30, choices=STATUS_CHOICES, default="pending")
    provider_response = models.TextField("پاسخ درگاه", blank=True)
    error_message = models.TextField("پیام خطا", blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    sent_at = models.DateTimeField("تاریخ ارسال", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ارسال‌کننده", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sms_logs",
    )

    class Meta:
        verbose_name = "پیامک"
        verbose_name_plural = "پیامک‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.get_status_display()}"


class BirthdaySmsSettings(models.Model):
    """تنظیمات پیامک خودکار تبریک تولد — تک‌رکورد."""

    is_enabled = models.BooleanField("فعال", default=False)
    message_template = models.TextField(
        "قالب پیام",
        default="تولدت مبارک {name}! از طرف {shop_name} بهترین‌ها را برایت آرزومندیم.",
    )
    shop_name = models.CharField("نام فروشگاه", max_length=100, default="سام اکسون")
    send_time = models.TimeField("ساعت ارسال", default=time(10, 0))
    last_run_date = models.DateField("آخرین ارسال خودکار", null=True, blank=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "تنظیمات پیامک تولد"
        verbose_name_plural = "تنظیمات پیامک تولد"

    def __str__(self):
        return "تنظیمات تبریک تولد"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BirthdaySmsExclusion(models.Model):
    """حذف موقت مشتری از لیست ارسال تولد در یک روز مشخص."""

    customer = models.ForeignKey(
        Customer,
        verbose_name="مشتری",
        on_delete=models.CASCADE,
        related_name="birthday_sms_exclusions",
    )
    exclude_date = models.DateField("تاریخ ارسال (روز جاری)")
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "استثناء پیامک تولد"
        verbose_name_plural = "استثناءهای پیامک تولد"
        unique_together = [("customer", "exclude_date")]

    def __str__(self):
        return f"{self.customer.full_name} — {self.exclude_date}"


class WalletTransaction(models.Model):
    """تراکنش کیف پول مشتری."""

    TYPE_CHOICES = [
        ("deposit", "واریز"),
        ("withdraw", "برداشت"),
        ("sale", "پرداخت فروش"),
        ("refund", "بازگشت"),
        ("adjustment", "اصلاح"),
    ]

    customer = models.ForeignKey(
        Customer,
        verbose_name="مشتری",
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    amount = models.DecimalField("مبلغ (مثبت=واریز)", **MONEY_KWARGS)
    balance_after = models.DecimalField("موجودی پس از تراکنش", **MONEY_KWARGS)
    transaction_type = models.CharField(
        "نوع", max_length=12, choices=TYPE_CHOICES, default="adjustment"
    )
    description = models.CharField("شرح", max_length=255, blank=True)
    sale = models.ForeignKey(
        "Sale",
        verbose_name="فروش مرتبط",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField("تاریخ", auto_now_add=True)

    class Meta:
        verbose_name = "تراکنش کیف پول"
        verbose_name_plural = "تراکنش‌های کیف پول"
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.customer.full_name} {sign}{self.amount}"


class SmsClubSettings(models.Model):
    """تنظیمات پیامک خودکار باشگاه مشتریان — تک‌رکورد."""

    DISCOUNT_TYPE_CHOICES = [
        ("amount", "مبلغ ثابت"),
        ("percent", "درصد"),
    ]

    shop_name = models.CharField("نام فروشگاه", max_length=100, default="سام اکسون")

    auto_order_placed = models.BooleanField("پیامک ثبت سفارش", default=True)
    auto_welcome = models.BooleanField("پیامک خوش‌آمدگویی", default=True)
    auto_level_up = models.BooleanField("پیامک ارتقای سطح", default=True)

    order_placed_template = models.TextField(
        "قالب ثبت سفارش",
        default="{name} عزیز، سفارش شما به مبلغ {amount} تومان ثبت شد. {shop_name}",
    )
    welcome_template = models.TextField(
        "قالب خوش‌آمدگویی",
        default="{name} عزیز، به باشگاه {shop_name} خوش آمدید! کد عضویت شما: {code}",
    )
    level_up_template = models.TextField(
        "قالب ارتقای سطح",
        default="{name} عزیز، سطح باشگاه شما به «{level}» ارتقا یافت. {shop_name}",
    )
    discount_template = models.TextField(
        "قالب تخفیف ویژه",
        default="{name} عزیز! تخفیف ویژه {discount_label} از {shop_name} — منتظر دیدار شما هستیم.",
    )

    default_discount_type = models.CharField(
        "نوع تخفیف پیش‌فرض", max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="amount"
    )
    default_discount_value = models.DecimalField(
        "مقدار تخفیف پیش‌فرض", default=0, **MONEY_KWARGS
    )
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "تنظیمات پیامک باشگاه"
        verbose_name_plural = "تنظیمات پیامک باشگاه"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ReminderCampaign(models.Model):
    """کمپین یادآوری دوره‌ای باشگاه — فقط مدیر سیستم."""

    name = models.CharField("نام کمپین", max_length=100)
    is_enabled = models.BooleanField("فعال", default=True)
    interval_months = models.PositiveIntegerField("هر چند ماه یک‌بار", default=3)
    message_template = models.TextField(
        "قالب پیام",
        default="{name} عزیز، {shop_name} دلتنگ شماست! کد باشگاه: {code} — سطح: {level}",
    )
    shop_name = models.CharField("نام فروشگاه", max_length=100, default="سام اکسون")
    loyalty_levels = models.ManyToManyField(
        LoyaltyLevel,
        verbose_name="سطوح هدف",
        blank=True,
        related_name="reminder_campaigns",
        help_text="خالی = همه سطوح",
    )
    min_months_since_purchase = models.PositiveIntegerField(
        "حداقل ماه از آخرین خرید",
        null=True,
        blank=True,
        help_text="اختیاری — فقط مشتریانی که حداقل این مدت خرید نکرده‌اند",
    )
    last_run_at = models.DateTimeField("آخرین اجرا", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "کمپین یادآوری"
        verbose_name_plural = "کمپین‌های یادآوری"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ReminderSendLog(models.Model):
    """ثبت ارسال یادآوری برای جلوگیری از تکرار در یک دوره."""

    campaign = models.ForeignKey(
        ReminderCampaign,
        verbose_name="کمپین",
        on_delete=models.CASCADE,
        related_name="send_logs",
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name="مشتری",
        on_delete=models.CASCADE,
        related_name="reminder_logs",
    )
    period_key = models.CharField("دوره", max_length=20)
    sent_at = models.DateTimeField("زمان ارسال", auto_now_add=True)

    class Meta:
        verbose_name = "لاگ یادآوری"
        verbose_name_plural = "لاگ‌های یادآوری"
        unique_together = [("campaign", "customer", "period_key")]

    def __str__(self):
        return f"{self.campaign.name} — {self.customer.full_name}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "ایجاد"),
        ("update", "ویرایش"),
        ("delete", "حذف"),
        ("approve", "تایید"),
        ("reject", "رد"),
        ("sale", "فروش"),
        ("payment", "دریافت پرداخت"),
        ("check_in", "ثبت حضور"),
        ("check_out", "پایان کار"),
        ("login", "ورود"),
        ("logout", "خروج"),
        ("sms", "پیامک"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField("عملیات", max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField("نوع موجودیت", max_length=50, blank=True)
    entity_id = models.CharField("شناسه", max_length=50, blank=True)
    message = models.CharField("شرح", max_length=500)
    details = models.JSONField("جزئیات", default=dict, blank=True)
    is_executive_only = models.BooleanField("فقط مدیر ارشد", default=False)
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        verbose_name = "لاگ فعالیت"
        verbose_name_plural = "لاگ‌های فعالیت"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
