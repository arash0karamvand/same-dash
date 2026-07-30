"""مدل‌های دامنه پروژه."""

from datetime import time
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from backend.soft_delete import SoftDeleteModel

MONEY_KWARGS = {"max_digits": 18, "decimal_places": 0}

BRANCH_CHOICES = [
    ("branch_1", "کمرد"),
    ("branch_2", "پاسداران"),
]


class Branch(models.Model):
    """شعبه فروشگاه — قابل مدیریت توسط مدیر سیستم."""

    code = models.SlugField("کد شعبه", max_length=40, unique=True)
    label = models.CharField("نام شعبه", max_length=80)
    color = models.CharField("رنگ", max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "شعبه"
        verbose_name_plural = "شعبه‌ها"
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class LookupOption(models.Model):
    """گزینه‌های قابل تنظیم — روش پرداخت، نوع سفارش و غیره."""

    category = models.CharField("دسته", max_length=40, db_index=True)
    code = models.CharField("کد", max_length=40)
    label = models.CharField("عنوان", max_length=80)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    meta = models.JSONField("متادیتا", default=dict, blank=True)

    class Meta:
        verbose_name = "گزینه سیستم"
        verbose_name_plural = "گزینه‌های سیستم"
        ordering = ["category", "sort_order", "label"]
        constraints = [
            models.UniqueConstraint(fields=["category", "code"], name="uniq_lookup_category_code"),
        ]

    def __str__(self):
        return f"{self.category}:{self.code}"


class MenuSection(models.Model):
    """بخش‌های منوی پنل — قابل مدیریت در دیتابیس."""

    section_id = models.SlugField("شناسه بخش", max_length=40, unique=True)
    label = models.CharField("عنوان", max_length=80)
    icon = models.CharField("آیکون", max_length=16, default="📄")
    page_key = models.SlugField("کلید صفحه", max_length=40)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    system_admin = models.BooleanField("فقط مدیر سیستم", default=False)
    menu_permission_codes = models.JSONField("مجوزهای منو", default=list)
    section_permission_codes = models.JSONField("مجوزهای بخش", default=list)

    class Meta:
        verbose_name = "بخش منو"
        verbose_name_plural = "بخش‌های منو"
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


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
    address = models.TextField("آدرس", blank=True)
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
    branch = models.CharField("شعبه", max_length=40, blank=True)
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
    grants_full_access = models.BooleanField("دسترسی کامل", default=False)
    is_locked = models.BooleanField("غیرقابل ویرایش", default=False)
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
    branch = models.CharField("شعبه", max_length=40, default="branch_1")
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
        ("check", "چک"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("paid", "پرداخت‌شده"),
        ("unpaid", "پرداخت‌نشده"),
        ("installment", "قسطی"),
    ]
    ORDER_KIND_CHOICES = [
        ("normal", "فروش عادی"),
        ("pre_invoice", "پیش‌فاکتور"),
        ("deposit", "بیعانیه"),
    ]
    ORDER_STATUS_CHOICES = [
        ("confirmed", "تایید شده"),
        ("pending", "در انتظار"),
        ("cancelled", "لغو شده"),
    ]

    ORDER_KIND_NORMAL = "normal"
    ORDER_KIND_PRE_INVOICE = "pre_invoice"
    ORDER_KIND_DEPOSIT = "deposit"
    ORDER_STATUS_CONFIRMED = "confirmed"
    ORDER_STATUS_PENDING = "pending"
    ORDER_STATUS_CANCELLED = "cancelled"

    WORKFLOW_STAGE_PENDING_BRANCH = "pending_branch"
    WORKFLOW_STAGE_BRANCH_APPROVED = "branch_approved"
    WORKFLOW_STAGE_ACCOUNTING_APPROVED = "accounting_approved"
    WORKFLOW_STAGE_IN_PRODUCTION = "in_production"
    WORKFLOW_STAGE_PRODUCTION_DONE = "production_done"
    WORKFLOW_STAGE_IN_FREIGHT = "in_freight"
    WORKFLOW_STAGE_COMPLETED = "completed"
    WORKFLOW_STAGE_CHOICES = [
        (WORKFLOW_STAGE_PENDING_BRANCH, "منتظر سرپرست شعبه"),
        (WORKFLOW_STAGE_BRANCH_APPROVED, "منتظر حسابداری"),
        (WORKFLOW_STAGE_ACCOUNTING_APPROVED, "ارسال به کارخانه"),
        (WORKFLOW_STAGE_IN_PRODUCTION, "در حال ساخت"),
        (WORKFLOW_STAGE_PRODUCTION_DONE, "آماده باربری"),
        (WORKFLOW_STAGE_IN_FREIGHT, "در باربری"),
        (WORKFLOW_STAGE_COMPLETED, "تکمیل شده"),
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
    discount = models.DecimalField("تخفیف (ریال)", default=0, **MONEY_KWARGS)
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
    ACCOUNTING_MODE_AUTOMATIC = "automatic"
    ACCOUNTING_MODE_MANUAL = "manual"
    ACCOUNTING_MODE_CHOICES = [
        (ACCOUNTING_MODE_AUTOMATIC, "حسابداری خودکار"),
        (ACCOUNTING_MODE_MANUAL, "حسابداری دستی"),
    ]
    accounting_mode = models.CharField(
        "نوع ثبت حسابداری",
        max_length=12,
        choices=ACCOUNTING_MODE_CHOICES,
        default=ACCOUNTING_MODE_AUTOMATIC,
    )
    order_kind = models.CharField(
        "نوع سفارش", max_length=12, choices=ORDER_KIND_CHOICES, default="normal"
    )
    order_status = models.CharField(
        "وضعیت سفارش", max_length=12, choices=ORDER_STATUS_CHOICES, default="confirmed"
    )
    delivery_date = models.DateField("تاریخ تحویل", null=True, blank=True)
    workflow_stage = models.CharField(
        "مرحله گردش کار",
        max_length=24,
        choices=WORKFLOW_STAGE_CHOICES,
        default=WORKFLOW_STAGE_COMPLETED,
        db_index=True,
    )
    branch_approved_at = models.DateTimeField("تاریخ تایید سرپرست", null=True, blank=True)
    branch_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده سرپرست",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="branch_approved_sales",
    )
    accounting_approved_at = models.DateTimeField("تاریخ تایید حسابداری", null=True, blank=True)
    accounting_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده حسابداری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_approved_sales",
    )
    factory_received_at = models.DateTimeField("دریافت کارخانه", null=True, blank=True)
    factory_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دریافت‌کننده کارخانه",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="factory_received_sales",
    )
    production_done_at = models.DateTimeField("پایان ساخت", null=True, blank=True)
    freight_received_at = models.DateTimeField("دریافت باربری", null=True, blank=True)
    freight_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دریافت‌کننده باربری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freight_received_sales",
    )
    freight_completed_at = models.DateTimeField("تکمیل باربری", null=True, blank=True)
    office_released_at = models.DateTimeField(
        "زمان انتشار برای اداری",
        null=True,
        blank=True,
        db_index=True,
    )
    factory_released_at = models.DateTimeField(
        "زمان انتشار برای کارخانه",
        null=True,
        blank=True,
        db_index=True,
    )
    transferred_to_office_at = models.DateTimeField(
        "انتقال به جدول اداری",
        null=True,
        blank=True,
        db_index=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_sales",
    )
    branch = models.CharField("شعبه", max_length=40, blank=True)
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
    received_at = models.DateField("تاریخ تحویل چک به شعبه", null=True, blank=True)
    receiver_name = models.CharField("تحویل‌گیرنده", max_length=120, blank=True)
    registration_account = models.ForeignKey(
        "Account",
        verbose_name="حساب ثبت چک",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="check_registrations",
    )
    deposit_account = models.ForeignKey(
        "Account",
        verbose_name="حساب واریز چک",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="check_deposits",
    )
    accounting_registered_at = models.DateTimeField("تاریخ ثبت حسابداری چک", null=True, blank=True)
    accounting_entry = models.ForeignKey(
        "AccountingEntry",
        verbose_name="سند ثبت چک",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installment_checks",
    )
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
    """فروشنده / مدیر — بدون نیاز به نام کاربری؛ اتصال اختیاری به حساب ورود."""

    STAFF_KIND_SELLER = "seller"
    STAFF_KIND_MANAGER = "manager"
    STAFF_KIND_CHOICES = [
        (STAFF_KIND_SELLER, "فروشنده"),
        (STAFF_KIND_MANAGER, "مدیر"),
    ]

    full_name = models.CharField("نام کامل", max_length=150)
    staff_kind = models.CharField(
        "نوع پرسنل",
        max_length=20,
        choices=STAFF_KIND_CHOICES,
        default=STAFF_KIND_SELLER,
        db_index=True,
    )
    branch = models.CharField("شعبه", max_length=40, default="branch_1")
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
    product_model = models.CharField("مدل", max_length=100, blank=True)
    fabric = models.CharField("پارچه", max_length=100, blank=True)
    description = models.TextField("توضیحات", blank=True)
    unit = models.CharField("واحد", max_length=20, default="عدد")
    attributes = models.JSONField("ویژگی‌های سفارشی", default=dict, blank=True)
    default_price = models.DecimalField("قیمت", default=0, **MONEY_KWARGS)
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
        return Decimal(self.default_price or 0)


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


class Material(SoftDeleteModel):
    """متریال / مواد اولیه — قیمت تمام‌شده و موجودی."""

    name = models.CharField("نام متریال", max_length=150)
    color_name = models.CharField("نام رنگ", max_length=50, blank=True)
    color_hex = models.CharField("کد رنگ", max_length=7, default="#cccccc")
    sku = models.CharField("کد", max_length=50, blank=True, db_index=True)
    unit = models.CharField("واحد", max_length=20, default="متر")
    unit_cost = models.DecimalField("قیمت واحد (تمام‌شده)", default=0, **MONEY_KWARGS)
    stock = models.DecimalField("موجودی", max_digits=12, decimal_places=2, null=True, blank=True)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    APPROVAL_PENDING = "pending"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "در انتظار تایید اداری"),
        (APPROVAL_APPROVED, "تایید شده"),
        (APPROVAL_REJECTED, "رد شده"),
    ]
    approval_status = models.CharField(
        "وضعیت تایید",
        max_length=16,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_APPROVED,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_materials",
    )
    approved_at = models.DateTimeField("تاریخ تایید", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_materials",
    )
    rejection_reason = models.TextField("دلیل رد", blank=True)
    inventory_accounted_at = models.DateTimeField("ثبت حسابداری موجودی", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        verbose_name = "متریال"
        verbose_name_plural = "متریال‌ها"
        ordering = ["name"]

    def __str__(self):
        if self.color_name:
            return f"{self.name} ({self.color_name})"
        return self.name


class ProductMaterial(models.Model):
    """ارتباط محصول با متریال — مقدار مصرف به ازای هر واحد محصول."""

    product = models.ForeignKey(
        Product,
        verbose_name="محصول",
        on_delete=models.CASCADE,
        related_name="product_materials",
    )
    material = models.ForeignKey(
        Material,
        verbose_name="متریال",
        on_delete=models.CASCADE,
        related_name="product_links",
    )
    quantity = models.DecimalField("مقدار مصرف", max_digits=12, decimal_places=3, default=1)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "متریال محصول"
        verbose_name_plural = "متریال‌های محصول"
        ordering = ["sort_order", "id"]
        unique_together = [("product", "material")]

    def __str__(self):
        return f"{self.product.name} ← {self.material.name} x{self.quantity}"


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
    product_model = models.CharField("مدل", max_length=100, blank=True)
    fabric = models.CharField("پارچه", max_length=100, blank=True)
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


class OfficeOrder(SoftDeleteModel):
    """صف اداری — فقط پس از تایید سرپرست شعبه در این جدول ایجاد می‌شود."""

    STATUS_PENDING = "pending_accounting"
    STATUS_RELEASED = "released_to_factory"
    STATUS_CHOICES = [
        (STATUS_PENDING, "منتظر تایید اداری"),
        (STATUS_RELEASED, "ارسال‌شده به کارخانه"),
    ]

    source_sale = models.OneToOneField(
        Sale,
        verbose_name="فروش مبدأ",
        on_delete=models.CASCADE,
        related_name="office_order",
    )
    customer = models.ForeignKey(
        Customer, verbose_name="مشتری", on_delete=models.CASCADE, related_name="office_orders"
    )
    amount = models.DecimalField("مبلغ فروش", **MONEY_KWARGS)
    discount_type = models.CharField(
        "نوع تخفیف", max_length=10, choices=Sale.DISCOUNT_TYPE_CHOICES, default="amount"
    )
    discount_value = models.DecimalField("مقدار تخفیف (ورودی)", default=0, **MONEY_KWARGS)
    discount = models.DecimalField("تخفیف (ریال)", default=0, **MONEY_KWARGS)
    final_amount = models.DecimalField("مبلغ نهایی", default=0, **MONEY_KWARGS)
    paid_amount = models.DecimalField("مبلغ پرداخت‌شده", default=0, **MONEY_KWARGS)
    sold_at = models.DateTimeField("تاریخ فروش", default=timezone.now)
    invoice_number = models.CharField("شماره فاکتور", max_length=40, blank=True)
    description = models.CharField("توضیحات", max_length=255, blank=True)
    payment_status = models.CharField(
        "وضعیت پرداخت", max_length=12, choices=Sale.PAYMENT_STATUS_CHOICES, default="paid"
    )
    payment_method = models.CharField(
        "روش پرداخت", max_length=10, choices=Sale.PAYMENT_METHOD_CHOICES, default="cash"
    )
    accounting_mode = models.CharField(
        "نوع ثبت حسابداری",
        max_length=12,
        choices=Sale.ACCOUNTING_MODE_CHOICES,
        default=Sale.ACCOUNTING_MODE_AUTOMATIC,
    )
    order_kind = models.CharField(
        "نوع سفارش", max_length=12, choices=Sale.ORDER_KIND_CHOICES, default="normal"
    )
    order_status = models.CharField(
        "وضعیت سفارش", max_length=12, choices=Sale.ORDER_STATUS_CHOICES, default="pending"
    )
    delivery_date = models.DateField("تاریخ تحویل", null=True, blank=True)
    branch = models.CharField("شعبه", max_length=40, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_office_orders",
    )
    seller = models.ForeignKey(
        "Seller",
        verbose_name="فروشنده",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="office_orders",
    )
    branch_approved_at = models.DateTimeField("تاریخ تایید سرپرست", null=True, blank=True)
    branch_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده سرپرست",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="branch_approved_office_orders",
    )
    accounting_approved_at = models.DateTimeField("تاریخ تایید اداری", null=True, blank=True)
    accounting_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده اداری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_approved_office_orders",
    )
    status = models.CharField(
        "وضعیت صف اداری",
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "سفارش اداری"
        verbose_name_plural = "سفارش‌های اداری"
        db_table = "office_orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"اداری {self.invoice_number or self.pk}"


class OfficeOrderLineItem(models.Model):
    office_order = models.ForeignKey(
        OfficeOrder, verbose_name="سفارش اداری", on_delete=models.CASCADE, related_name="line_items"
    )
    product = models.ForeignKey(
        Product, verbose_name="محصول", null=True, blank=True, on_delete=models.SET_NULL
    )
    variant = models.ForeignKey(
        ProductVariant, verbose_name="تنوع", null=True, blank=True, on_delete=models.SET_NULL
    )
    product_name = models.CharField("نام محصول", max_length=150)
    product_model = models.CharField("مدل", max_length=100, blank=True)
    fabric = models.CharField("پارچه", max_length=100, blank=True)
    color_name = models.CharField("رنگ", max_length=50, blank=True)
    color_hex = models.CharField("کد رنگ", max_length=7, blank=True)
    quantity = models.PositiveIntegerField("تعداد", default=1)
    unit_price = models.DecimalField("قیمت واحد", **MONEY_KWARGS)
    line_total = models.DecimalField("جمع ردیف", **MONEY_KWARGS)

    class Meta:
        verbose_name = "ردیف سفارش اداری"
        verbose_name_plural = "ردیف‌های سفارش اداری"
        db_table = "office_order_line_items"


class OfficeOrderInstallment(SoftDeleteModel):
    office_order = models.ForeignKey(
        OfficeOrder, verbose_name="سفارش اداری", on_delete=models.CASCADE, related_name="installments"
    )
    amount = models.DecimalField("مبلغ قسط", **MONEY_KWARGS)
    due_date = models.DateField("تاریخ سررسید")
    payment_method = models.CharField(
        "روش پرداخت", max_length=10, choices=Sale.PAYMENT_METHOD_CHOICES, default="cash"
    )
    check_number = models.CharField("شماره چک", max_length=50, blank=True)
    bank_name = models.CharField("نام بانک", max_length=100, blank=True)
    status = models.CharField(
        "وضعیت", max_length=12, choices=SaleInstallment.STATUS_CHOICES, default="pending"
    )
    paid_at = models.DateTimeField("تاریخ پرداخت", null=True, blank=True)
    notes = models.CharField("توضیحات", max_length=255, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "قسط سفارش اداری"
        verbose_name_plural = "اقساط سفارش اداری"
        db_table = "office_order_installments"
        ordering = ["due_date"]


class FactoryOrder(SoftDeleteModel):
    """صف کارخانه — فقط پس از تایید اداری در این جدول ایجاد می‌شود."""

    WORKFLOW_STAGE_ACCOUNTING_APPROVED = "accounting_approved"
    WORKFLOW_STAGE_IN_PRODUCTION = "in_production"
    WORKFLOW_STAGE_PRODUCTION_DONE = "production_done"
    WORKFLOW_STAGE_IN_FREIGHT = "in_freight"
    WORKFLOW_STAGE_COMPLETED = "completed"
    WORKFLOW_STAGE_CHOICES = [
        (WORKFLOW_STAGE_ACCOUNTING_APPROVED, "ارسال به کارخانه"),
        (WORKFLOW_STAGE_IN_PRODUCTION, "در حال ساخت"),
        (WORKFLOW_STAGE_PRODUCTION_DONE, "آماده باربری"),
        (WORKFLOW_STAGE_IN_FREIGHT, "در باربری"),
        (WORKFLOW_STAGE_COMPLETED, "تکمیل شده"),
    ]

    source_office_order = models.OneToOneField(
        OfficeOrder,
        verbose_name="سفارش اداری مبدأ",
        on_delete=models.CASCADE,
        related_name="factory_order",
    )
    source_sale = models.ForeignKey(
        Sale,
        verbose_name="فروش مبدأ",
        on_delete=models.CASCADE,
        related_name="factory_orders",
    )
    customer = models.ForeignKey(
        Customer, verbose_name="مشتری", on_delete=models.CASCADE, related_name="factory_orders"
    )
    invoice_number = models.CharField("شماره فاکتور", max_length=40, blank=True)
    description = models.CharField("توضیحات", max_length=255, blank=True)
    delivery_date = models.DateField("تاریخ تحویل", null=True, blank=True)
    branch = models.CharField("شعبه", max_length=40, blank=True)
    order_kind = models.CharField(
        "نوع سفارش", max_length=12, choices=Sale.ORDER_KIND_CHOICES, default="normal"
    )
    workflow_stage = models.CharField(
        "مرحله کارخانه",
        max_length=24,
        choices=WORKFLOW_STAGE_CHOICES,
        default=WORKFLOW_STAGE_ACCOUNTING_APPROVED,
        db_index=True,
    )
    accounting_approved_at = models.DateTimeField("تاریخ تایید اداری", null=True, blank=True)
    accounting_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تاییدکننده اداری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_approved_factory_orders",
    )
    factory_received_at = models.DateTimeField("دریافت کارخانه", null=True, blank=True)
    factory_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دریافت‌کننده کارخانه",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="factory_received_orders",
    )
    production_done_at = models.DateTimeField("پایان ساخت", null=True, blank=True)
    materials_deducted_at = models.DateTimeField("کسر متریال", null=True, blank=True)
    freight_received_at = models.DateTimeField("دریافت باربری", null=True, blank=True)
    freight_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="دریافت‌کننده باربری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freight_received_orders",
    )
    freight_completed_at = models.DateTimeField("تکمیل باربری", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "سفارش کارخانه"
        verbose_name_plural = "سفارش‌های کارخانه"
        db_table = "factory_orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"کارخانه {self.invoice_number or self.pk}"


class FactoryOrderLineItem(models.Model):
    factory_order = models.ForeignKey(
        FactoryOrder, verbose_name="سفارش کارخانه", on_delete=models.CASCADE, related_name="line_items"
    )
    product = models.ForeignKey(
        Product, verbose_name="محصول", null=True, blank=True, on_delete=models.SET_NULL
    )
    variant = models.ForeignKey(
        ProductVariant, verbose_name="تنوع", null=True, blank=True, on_delete=models.SET_NULL
    )
    product_name = models.CharField("نام محصول", max_length=150)
    product_model = models.CharField("مدل", max_length=100, blank=True)
    fabric = models.CharField("پارچه", max_length=100, blank=True)
    color_name = models.CharField("رنگ", max_length=50, blank=True)
    color_hex = models.CharField("کد رنگ", max_length=7, blank=True)
    quantity = models.PositiveIntegerField("تعداد", default=1)

    class Meta:
        verbose_name = "ردیف سفارش کارخانه"
        verbose_name_plural = "ردیف‌های سفارش کارخانه"
        db_table = "factory_order_line_items"


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
        "شعبه کاری", max_length=40, blank=True,
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


class Account(models.Model):
    """حساب دفتر کل — طرح حساب."""

    CLASS_CHOICES = [
        ("asset", "دارایی"),
        ("liability", "بدهی"),
        ("equity", "سرمایه"),
        ("revenue", "درآمد"),
        ("expense", "هزینه"),
    ]
    NORMAL_BALANCE_CHOICES = [
        ("debit", "بدهکار"),
        ("credit", "بستانکار"),
    ]

    slug = models.SlugField("شناسه", max_length=60, unique=True)
    code = models.CharField("کد حساب کل", max_length=10, blank=True, db_index=True)
    name = models.CharField("نام حساب", max_length=120)
    account_class = models.CharField("طبقه", max_length=20, choices=CLASS_CHOICES)
    normal_balance = models.CharField("ماهیت", max_length=10, choices=NORMAL_BALANCE_CHOICES)
    sort_order = models.PositiveSmallIntegerField("ترتیب", default=0)
    legacy_entry_type = models.CharField("نوع سند قدیمی", max_length=20, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "حساب کل"
        verbose_name_plural = "حساب‌های کل"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class SubsidiaryAccount(models.Model):
    """حساب معین — زیرمجموعه حساب کل."""

    account = models.ForeignKey(
        Account,
        verbose_name="حساب کل",
        on_delete=models.PROTECT,
        related_name="subsidiaries",
    )
    code = models.CharField("کد معین", max_length=10)
    name = models.CharField("عنوان حساب", max_length=120)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "حساب معین"
        verbose_name_plural = "حساب‌های معین"
        ordering = ["account__sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["account", "code"], name="uniq_subsidiary_account_code"),
        ]

    @property
    def full_code(self):
        base = (self.account.code or str(self.account.sort_order)).strip()
        return f"{base}/{self.code}"

    def __str__(self):
        return self.name


class DetailedAccount(models.Model):
    """حساب تفصیلی — زیرمجموعه حساب معین."""

    subsidiary = models.ForeignKey(
        SubsidiaryAccount,
        verbose_name="حساب معین",
        on_delete=models.PROTECT,
        related_name="details",
    )
    code = models.CharField("کد تفصیلی", max_length=10)
    name = models.CharField("عنوان حساب", max_length=120)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "حساب تفصیلی"
        verbose_name_plural = "حساب‌های تفصیلی"
        ordering = ["subsidiary__account__sort_order", "subsidiary__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["subsidiary", "code"], name="uniq_detailed_account_code"),
        ]

    @property
    def full_code(self):
        return f"{self.subsidiary.full_code}/{self.code}"

    def __str__(self):
        return self.name


class AccountingEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("manual", "دستی"),
        ("sale", "فروش"),
        ("receivable", "دریافتنی"),
        ("payment", "دریافت / پرداخت"),
        ("refund", "برگشت"),
        ("adjustment", "تعدیل"),
        ("other", "سایر"),
    ]

    entry_type = models.CharField(
        "نوع سند", max_length=20, choices=ENTRY_TYPE_CHOICES, default="sale"
    )
    account = models.ForeignKey(
        Account,
        verbose_name="حساب کل",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    subsidiary = models.ForeignKey(
        SubsidiaryAccount,
        verbose_name="حساب معین",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    detailed = models.ForeignKey(
        DetailedAccount,
        verbose_name="حساب تفصیلی",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    debit = models.DecimalField("بدهکار", default=0, **MONEY_KWARGS)
    credit = models.DecimalField("بستانکار", default=0, **MONEY_KWARGS)
    amount = models.DecimalField("مبلغ", default=0, **MONEY_KWARGS)
    document_code = models.CharField("کد سند", max_length=30, blank=True, db_index=True)
    document_number = models.PositiveIntegerField("شماره سند", null=True, blank=True, db_index=True)
    attach_code = models.CharField("ع", max_length=40, blank=True)
    general_account = models.CharField("حساب کل", max_length=120, blank=True)
    subsidiary_account = models.CharField("حساب معین", max_length=120, blank=True)
    detailed_account = models.CharField("حساب تفصیلی", max_length=120, blank=True)
    opening_debit = models.DecimalField("مانده ابتدای دوره (بدهکار)", default=0, **MONEY_KWARGS)
    opening_credit = models.DecimalField("مانده ابتدای دوره (بستانکار)", default=0, **MONEY_KWARGS)
    balance_debit = models.DecimalField("مانده بدهکار", default=0, **MONEY_KWARGS)
    balance_credit = models.DecimalField("مانده بستانکار", default=0, **MONEY_KWARGS)
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


class UserAccountingPreference(models.Model):
    """ترجیحات حسابداری کاربر — حساب پیش‌فرض ثبت/واریز چک."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        on_delete=models.CASCADE,
        related_name="accounting_preference",
    )
    default_check_registration_account = models.ForeignKey(
        Account,
        verbose_name="حساب پیش‌فرض ثبت چک",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_for_check_registration",
    )
    default_check_deposit_account = models.ForeignKey(
        Account,
        verbose_name="حساب پیش‌فرض واریز چک",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_for_check_deposit",
    )
    updated_at = models.DateTimeField("به‌روزرسانی", auto_now=True)

    class Meta:
        verbose_name = "ترجیح حسابداری کاربر"
        verbose_name_plural = "ترجیحات حسابداری کاربران"

    def __str__(self):
        return f"ترجیحات حسابداری — {self.user}"


class FactoryAccount(models.Model):
    """حساب کل — دفتر حسابداری کارخانه (جدول مجزا)."""

    CLASS_CHOICES = Account.CLASS_CHOICES
    NORMAL_BALANCE_CHOICES = Account.NORMAL_BALANCE_CHOICES

    slug = models.SlugField("شناسه", max_length=60, unique=True)
    code = models.CharField("کد حساب کل", max_length=10, blank=True, db_index=True)
    name = models.CharField("نام حساب", max_length=120)
    account_class = models.CharField("طبقه", max_length=20, choices=CLASS_CHOICES)
    normal_balance = models.CharField("ماهیت", max_length=10, choices=NORMAL_BALANCE_CHOICES)
    sort_order = models.PositiveSmallIntegerField("ترتیب", default=0)
    legacy_entry_type = models.CharField("نوع سند قدیمی", max_length=20, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        db_table = "factory_accounts"
        verbose_name = "حساب کل کارخانه"
        verbose_name_plural = "حساب‌های کل کارخانه"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class FactorySubsidiaryAccount(models.Model):
    """حساب معین — دفتر حسابداری کارخانه."""

    account = models.ForeignKey(
        FactoryAccount,
        verbose_name="حساب کل",
        on_delete=models.PROTECT,
        related_name="subsidiaries",
    )
    code = models.CharField("کد معین", max_length=10)
    name = models.CharField("عنوان حساب", max_length=120)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        db_table = "factory_subsidiary_accounts"
        verbose_name = "حساب معین کارخانه"
        verbose_name_plural = "حساب‌های معین کارخانه"
        ordering = ["account__sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["account", "code"], name="uniq_factory_subsidiary_account_code"),
        ]

    @property
    def full_code(self):
        base = (self.account.code or str(self.account.sort_order)).strip()
        return f"{base}/{self.code}"

    def __str__(self):
        return self.name


class FactoryDetailedAccount(models.Model):
    """حساب تفصیلی — دفتر حسابداری کارخانه."""

    subsidiary = models.ForeignKey(
        FactorySubsidiaryAccount,
        verbose_name="حساب معین",
        on_delete=models.PROTECT,
        related_name="details",
    )
    code = models.CharField("کد تفصیلی", max_length=10)
    name = models.CharField("عنوان حساب", max_length=120)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        db_table = "factory_detailed_accounts"
        verbose_name = "حساب تفصیلی کارخانه"
        verbose_name_plural = "حساب‌های تفصیلی کارخانه"
        ordering = ["subsidiary__account__sort_order", "subsidiary__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["subsidiary", "code"], name="uniq_factory_detailed_account_code"),
        ]

    @property
    def full_code(self):
        return f"{self.subsidiary.full_code}/{self.code}"

    def __str__(self):
        return self.name


class FactoryAccountingEntry(models.Model):
    """سند حسابداری کارخانه — جدول مجزا، بدون اتصال به دفتر اداری."""

    ENTRY_TYPE_CHOICES = AccountingEntry.ENTRY_TYPE_CHOICES

    entry_type = models.CharField(
        "نوع سند", max_length=20, choices=ENTRY_TYPE_CHOICES, default="adjustment"
    )
    account = models.ForeignKey(
        FactoryAccount,
        verbose_name="حساب کل",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    subsidiary = models.ForeignKey(
        FactorySubsidiaryAccount,
        verbose_name="حساب معین",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    detailed = models.ForeignKey(
        FactoryDetailedAccount,
        verbose_name="حساب تفصیلی",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    debit = models.DecimalField("بدهکار", default=0, **MONEY_KWARGS)
    credit = models.DecimalField("بستانکار", default=0, **MONEY_KWARGS)
    amount = models.DecimalField("مبلغ", default=0, **MONEY_KWARGS)
    document_code = models.CharField("کد سند", max_length=30, blank=True, db_index=True)
    document_number = models.PositiveIntegerField("شماره سند", null=True, blank=True, db_index=True)
    attach_code = models.CharField("ع", max_length=40, blank=True)
    general_account = models.CharField("حساب کل", max_length=120, blank=True)
    subsidiary_account = models.CharField("حساب معین", max_length=120, blank=True)
    detailed_account = models.CharField("حساب تفصیلی", max_length=120, blank=True)
    opening_debit = models.DecimalField("مانده ابتدای دوره (بدهکار)", default=0, **MONEY_KWARGS)
    opening_credit = models.DecimalField("مانده ابتدای دوره (بستانکار)", default=0, **MONEY_KWARGS)
    balance_debit = models.DecimalField("مانده بدهکار", default=0, **MONEY_KWARGS)
    balance_credit = models.DecimalField("مانده بستانکار", default=0, **MONEY_KWARGS)
    entry_date = models.DateTimeField("تاریخ سند", default=timezone.now)
    description = models.CharField("توضیحات", max_length=255, blank=True)
    factory_order = models.ForeignKey(
        "FactoryOrder",
        verbose_name="سفارش کارخانه",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounting_entries",
    )
    is_approved = models.BooleanField("تایید حسابداری", default=False)
    transferred_to_office_at = models.DateTimeField(
        "انتقال به اداری",
        null=True,
        blank=True,
        db_index=True,
    )
    office_document_code = models.CharField("کد سند اداری", max_length=40, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        db_table = "factory_accounting_entries"
        verbose_name = "سند حسابداری کارخانه"
        verbose_name_plural = "اسناد حسابداری کارخانه"
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
        default="{name} عزیز، سفارش شما به مبلغ {amount} ریال ثبت شد. {shop_name}",
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
