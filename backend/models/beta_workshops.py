"""واحدهای کارگاهی بتا — نجاری، رنگ، رویه‌کوبی، پارچه، کنترل کیفیت."""

from django.db import models

from backend.soft_delete import SoftDeleteModel
from .base import MONEY_KWARGS, QUANTITY_KWARGS


class BetaCarpentryWorkshop(SoftDeleteModel):
    KIND_INTERNAL = "internal"
    KIND_SATELLITE = "satellite"
    KIND_CHOICES = [
        (KIND_INTERNAL, "داخل کارخانه"),
        (KIND_SATELLITE, "کارگاه اقماری"),
    ]

    name = models.CharField("نام واحد", max_length=150)
    kind = models.CharField("نوع", max_length=20, choices=KIND_CHOICES, default=KIND_INTERNAL)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "واحد نجاری (بتا)"
        verbose_name_plural = "واحدهای نجاری (بتا)"

    def __str__(self):
        return self.name


class BetaCarpentryOrder(SoftDeleteModel):
    KIND_BUILD = "build"
    KIND_REPAIR = "repair"
    KIND_CHOICES = [
        (KIND_BUILD, "ساخت کلاف"),
        (KIND_REPAIR, "تعمیرات"),
    ]

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_READY = "ready"
    STATUS_DELIVERED = "delivered"
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, "در حال ساخت / تعمیر"),
        (STATUS_READY, "آماده تحویل"),
        (STATUS_DELIVERED, "تحویل شده به انبار"),
    ]

    code = models.CharField("کد دستور", max_length=40, unique=True)
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    kind = models.CharField("نوع", max_length=20, choices=KIND_CHOICES, default=KIND_BUILD)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_carpentry_orders",
    )
    frame = models.ForeignKey(
        "backend.Frame",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_carpentry_orders",
    )
    customer_name = models.CharField("مشتری", max_length=150, blank=True, default="")
    order_ref = models.CharField("شماره سفارش", max_length=80, blank=True, default="")
    product_name = models.CharField("نام محصول / مدل کلاف", max_length=200)
    wood_type = models.CharField("جنس چوب", max_length=80, blank=True, default="")
    quantity = models.PositiveIntegerField("تیراژ", default=1)
    due_date = models.DateField("موعد تحویل", null=True, blank=True)
    freight_cost = models.DecimalField("هزینه باربری", **MONEY_KWARGS, default=0)
    status = models.CharField("وضعیت ساخت", max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    notes_log = models.JSONField("نظرات و آپدیت‌ها", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "دستور نجاری (بتا)"
        verbose_name_plural = "دستورهای نجاری (بتا)"

    def __str__(self):
        return self.code


class BetaCarpentryTool(SoftDeleteModel):
    STATUS_ACTIVE = "active"
    STATUS_MAINTENANCE = "maintenance"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "فعال"),
        (STATUS_MAINTENANCE, "در تعمیر"),
        (STATUS_RETIRED, "اسقاط"),
    ]

    code = models.CharField("کد", max_length=40, unique=True)
    name = models.CharField("نام ابزار / دستگاه", max_length=150)
    category = models.CharField("دسته", max_length=80, blank=True, default="")
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tools",
    )
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    quantity = models.PositiveIntegerField("تعداد", default=1)
    purchase_date = models.DateField("تاریخ تحویل", null=True, blank=True)
    value = models.DecimalField("ارزش", **MONEY_KWARGS, default=0)
    note = models.TextField("توضیحات", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "ابزار نجاری (بتا)"
        verbose_name_plural = "ابزارهای نجاری (بتا)"

    def __str__(self):
        return self.name


class BetaCarpentryWoodPurchase(SoftDeleteModel):
    code = models.CharField("کد خرید", max_length=40, unique=True)
    supplier = models.CharField("تامین‌کننده", max_length=150, blank=True, default="")
    material_type = models.CharField("نوع متریال", max_length=80, blank=True, default="")
    wood_type = models.CharField("جنس چوب", max_length=80, blank=True, default="")
    quantity = models.DecimalField("مقدار", **QUANTITY_KWARGS, default=0)
    unit = models.CharField("واحد", max_length=20, blank=True, default="متر")
    unit_cost = models.DecimalField("بهای واحد", **MONEY_KWARGS, default=0)
    total_cost = models.DecimalField("مبلغ کل", **MONEY_KWARGS, default=0)
    purchase_date = models.DateField("تاریخ خرید", null=True, blank=True)
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wood_purchases",
    )
    invoice_ref = models.CharField("شماره فاکتور", max_length=80, blank=True, default="")
    note = models.TextField("توضیحات", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "خرید چوب نجاری (بتا)"
        verbose_name_plural = "خریدهای چوب نجاری (بتا)"

    def __str__(self):
        return self.code


class BetaCarpentryExternalService(SoftDeleteModel):
    code = models.CharField("کد خدمت", max_length=40, unique=True)
    service_type = models.CharField("نوع خدمت", max_length=80, blank=True, default="")
    provider = models.CharField("پیمانکار / ارائه‌دهنده", max_length=150, blank=True, default="")
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="external_services",
    )
    carpentry_order = models.ForeignKey(
        BetaCarpentryOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="external_services",
    )
    amount = models.DecimalField("مبلغ", **MONEY_KWARGS, default=0)
    service_date = models.DateField("تاریخ", null=True, blank=True)
    description = models.TextField("شرح", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "خدمت برون‌سازمانی نجاری (بتا)"
        verbose_name_plural = "خدمات برون‌سازمانی نجاری (بتا)"

    def __str__(self):
        return self.code


class BetaCarpentryFreight(SoftDeleteModel):
    code = models.CharField("کد حمل", max_length=40, unique=True)
    carpentry_order = models.ForeignKey(
        BetaCarpentryOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freight_records",
    )
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freight_records",
    )
    destination = models.CharField("مقصد", max_length=150, blank=True, default="")
    driver_name = models.CharField("راننده / باربری", max_length=120, blank=True, default="")
    cost = models.DecimalField("هزینه", **MONEY_KWARGS, default=0)
    sent_date = models.DateField("تاریخ ارسال", null=True, blank=True)
    note = models.TextField("توضیحات", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "باربری نجاری (بتا)"
        verbose_name_plural = "باربری‌های نجاری (بتا)"

    def __str__(self):
        return self.code


class BetaCarpentryAttendance(SoftDeleteModel):
    workshop = models.ForeignKey(
        BetaCarpentryWorkshop,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    person_name = models.CharField("نام پرسنل", max_length=120)
    visit_date = models.DateField("تاریخ")
    check_in = models.TimeField("ورود", null=True, blank=True)
    check_out = models.TimeField("خروج", null=True, blank=True)
    note = models.TextField("توضیحات", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-visit_date", "-id"]
        verbose_name = "تردد نجاری (بتا)"
        verbose_name_plural = "ترددهای نجاری (بتا)"

    def __str__(self):
        return f"{self.person_name} — {self.visit_date}"


class BetaPaintOrder(SoftDeleteModel):
    KIND_NORMAL = "normal"
    KIND_REPAIR = "repair"
    KIND_QC_RETURN = "qc_return"
    KIND_CHOICES = [
        (KIND_NORMAL, "تولید عادی"),
        (KIND_REPAIR, "تعمیرات کارخانه"),
        (KIND_QC_RETURN, "برگشتی QC"),
    ]

    STAGE_RAW = "raw"
    STAGE_SANDING = "sanding"
    STAGE_PUTTY = "putty"
    STAGE_SEALER = "sealer"
    STAGE_TOPCOAT = "topcoat"
    STAGE_PATINA = "patina"
    STAGE_PU_FINAL = "pu_final"
    STAGE_QC = "qc"
    STAGE_CHOICES = [
        (STAGE_RAW, "ورود کلاف خام"),
        (STAGE_SANDING, "سنباده و زیرسازی"),
        (STAGE_PUTTY, "بتونه و آستر اول"),
        (STAGE_SEALER, "سیلر و پوستاب"),
        (STAGE_TOPCOAT, "رنگ رویه اصلی"),
        (STAGE_PATINA, "پتینه و هایلایت"),
        (STAGE_PU_FINAL, "پلی‌اورتان نهایی"),
        (STAGE_QC, "کنترل کیفیت و تحویل"),
    ]
    STAGE_ORDER = [
        STAGE_RAW,
        STAGE_SANDING,
        STAGE_PUTTY,
        STAGE_SEALER,
        STAGE_TOPCOAT,
        STAGE_PATINA,
        STAGE_PU_FINAL,
        STAGE_QC,
    ]

    code = models.CharField("کد سفارش رنگ", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_paint_orders",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    kind = models.CharField("نوع سفارش", max_length=20, choices=KIND_CHOICES, default=KIND_NORMAL)
    color_name = models.CharField("فام رنگ", max_length=80, blank=True, default="")
    stage = models.CharField("مرحله خط", max_length=20, choices=STAGE_CHOICES, default=STAGE_RAW)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    qc_issue = models.TextField("ایراد QC", blank=True, default="")
    notes_log = models.JSONField("لاگ و یادداشت‌ها", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "سفارش رنگ (بتا)"
        verbose_name_plural = "سفارش‌های رنگ (بتا)"

    def __str__(self):
        return self.code


class BetaFoamJob(SoftDeleteModel):
    STAGE_QUEUE = "queue"
    STAGE_CUT = "cut"
    STAGE_INSTALL = "install"
    STAGE_DONE = "done"
    STAGE_CHOICES = [
        (STAGE_QUEUE, "صف برش"),
        (STAGE_CUT, "برش فوم"),
        (STAGE_INSTALL, "نصب روی کلاف"),
        (STAGE_DONE, "آماده رویه‌کوبی"),
    ]
    STAGE_ORDER = [STAGE_QUEUE, STAGE_CUT, STAGE_INSTALL, STAGE_DONE]

    code = models.CharField("کد کار فوم", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_foam_jobs",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    foam_name = models.CharField("دستور فوم", max_length=150, blank=True, default="")
    stage = models.CharField("مرحله", max_length=20, choices=STAGE_CHOICES, default=STAGE_QUEUE)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    notes_log = models.JSONField("لاگ", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "کار فوم"
        verbose_name_plural = "کارهای فوم"

    def __str__(self):
        return self.code


class BetaCushionJob(SoftDeleteModel):
    STAGE_QUEUE = "queue"
    STAGE_CUT = "cut"
    STAGE_SEW = "sew"
    STAGE_DONE = "done"
    STAGE_CHOICES = [
        (STAGE_QUEUE, "صف دوخت"),
        (STAGE_CUT, "برش پارچه کوسن"),
        (STAGE_SEW, "دوخت و پر کردن"),
        (STAGE_DONE, "آماده مونتاژ"),
    ]
    STAGE_ORDER = [STAGE_QUEUE, STAGE_CUT, STAGE_SEW, STAGE_DONE]

    code = models.CharField("کد کار کوسن", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_cushion_jobs",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    cushion_name = models.CharField("دستور کوسن", max_length=150, blank=True, default="")
    stage = models.CharField("مرحله", max_length=20, choices=STAGE_CHOICES, default=STAGE_QUEUE)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    notes_log = models.JSONField("لاگ", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "کار کوسن"
        verbose_name_plural = "کارهای کوسن"

    def __str__(self):
        return self.code


class BetaFabricNeed(SoftDeleteModel):
    STATUS_PENDING = "pending"
    STATUS_RESERVED = "reserved"
    STATUS_ISSUED = "issued"
    STATUS_CHOICES = [
        (STATUS_PENDING, "نیاز ثبت‌شده"),
        (STATUS_RESERVED, "رزرو شده"),
        (STATUS_ISSUED, "حواله شده"),
    ]

    code = models.CharField("کد نیاز پارچه", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_fabric_needs",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    color_name = models.CharField("رنگ پارچه", max_length=80, blank=True, default="")
    recipe_name = models.CharField("دستور پارچه", max_length=150, blank=True, default="")
    meters = models.DecimalField("متراژ مورد نیاز", **QUANTITY_KWARGS, default=0)
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "نیاز پارچه خط تولید"
        verbose_name_plural = "نیازهای پارچه خط تولید"

    def __str__(self):
        return self.code


class BetaUpholsteryJob(SoftDeleteModel):
    STAGE_WEBBING = "webbing"
    STAGE_FOAM = "foam"
    STAGE_FABRIC = "fabric"
    STAGE_FINISHING = "finishing"
    STAGE_QC = "qc"
    STAGE_CHOICES = [
        (STAGE_WEBBING, "تسمه‌کشی و فنربندی"),
        (STAGE_FOAM, "نصب فوم سرد و اسفنج"),
        (STAGE_FABRIC, "کشیدن پارچه و لمسه‌دوزی"),
        (STAGE_FINISHING, "میخ‌کاری، سرمه‌دوزی و اتوکشی"),
        (STAGE_QC, "تکمیل و ارسال به کنترل کیفیت (QC)"),
    ]
    STAGE_ORDER = [
        STAGE_WEBBING,
        STAGE_FOAM,
        STAGE_FABRIC,
        STAGE_FINISHING,
        STAGE_QC,
    ]

    code = models.CharField("شناسه کار", max_length=40, unique=True)
    order_ref = models.CharField("شماره سفارش", max_length=80, blank=True, default="")
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_upholstery_jobs",
    )
    product_name = models.CharField("مدل مبلمان", max_length=200)
    foam_material = models.CharField("متریال فوم و نشیمن", max_length=200, blank=True, default="")
    craftsman = models.CharField("استادکار رویه‌کوب", max_length=120, blank=True, default="")
    stage = models.CharField("مرحله فنی", max_length=20, choices=STAGE_CHOICES, default=STAGE_WEBBING)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    due_date = models.DateField("موعد تحویل", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "کار رویه‌کوبی (بتا)"
        verbose_name_plural = "کارهای رویه‌کوبی (بتا)"

    def __str__(self):
        return self.code


class BetaFabricRoll(SoftDeleteModel):
    code = models.CharField("کد پارچه", max_length=40, unique=True)
    color_name = models.CharField("رنگ", max_length=80, blank=True, default="")
    company = models.CharField("شرکت / برند", max_length=120, blank=True, default="")
    fabric_type = models.CharField("جنس پارچه", max_length=80, blank=True, default="")
    country = models.CharField("کشور سازنده", max_length=80, blank=True, default="")
    unit_cost = models.DecimalField("بهای خرید هر متر", **MONEY_KWARGS, default=0)
    meters = models.DecimalField("متراژ", **QUANTITY_KWARGS, default=0)
    image_url = models.URLField("تصویر", blank=True, default="")
    min_meters = models.DecimalField("حداقل موجودی", **QUANTITY_KWARGS, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "طاقه پارچه (بتا)"
        verbose_name_plural = "طاقه‌های پارچه (بتا)"

    def __str__(self):
        return self.code


class BetaFabricDispatch(SoftDeleteModel):
    code = models.CharField("شماره حواله", max_length=40, unique=True)
    roll = models.ForeignKey(
        BetaFabricRoll,
        on_delete=models.PROTECT,
        related_name="dispatches",
    )
    destination = models.CharField("کارگاه مقصد", max_length=150)
    meters = models.DecimalField("متراژ ارسالی", **QUANTITY_KWARGS)
    sent_date = models.DateField("تاریخ ارسال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "حواله خروج پارچه (بتا)"
        verbose_name_plural = "حواله‌های خروج پارچه (بتا)"

    def __str__(self):
        return self.code


class BetaQcInspection(SoftDeleteModel):
    STATUS_PENDING = "pending"
    STATUS_REWORK = "rework"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار بازرسی"),
        (STATUS_REWORK, "نیازمند بازکاری"),
        (STATUS_APPROVED, "تایید شده"),
    ]

    GRADE_A = "A"
    GRADE_B = "B"
    GRADE_C = "C"
    GRADE_CHOICES = [
        (GRADE_A, "Grade A"),
        (GRADE_B, "Grade B"),
        (GRADE_C, "Grade C"),
    ]

    code = models.CharField("کد بازرسی", max_length=40, unique=True)
    order_ref = models.CharField("شماره سفارش", max_length=80, blank=True, default="")
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_qc_inspections",
    )
    buyer_name = models.CharField("خریدار", max_length=150, blank=True, default="")
    invoice_ref = models.CharField("فاکتور", max_length=80, blank=True, default="")
    origin = models.CharField("مبدا ساخت", max_length=150, blank=True, default="")
    product_name = models.CharField("محصول", max_length=200)
    requirements = models.TextField("الزامات", blank=True, default="")
    quantity = models.PositiveIntegerField("تیراژ", default=1)
    wood_color = models.CharField("رنگ چوب", max_length=80, blank=True, default="")
    fabric_color = models.CharField("پارچه", max_length=80, blank=True, default="")
    status = models.CharField("وضعیت بررسی", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    grade = models.CharField("گرید", max_length=4, choices=GRADE_CHOICES, blank=True, default="")
    scan_url = models.URLField("برگه اسکن", blank=True, default="")
    entered_at = models.DateField("تاریخ ورود به QC", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "بازرسی کنترل کیفیت (بتا)"
        verbose_name_plural = "بازرسی‌های کنترل کیفیت (بتا)"

    def __str__(self):
        return self.code


class BetaAssemblyJob(SoftDeleteModel):
    STAGE_QUEUE = "queue"
    STAGE_ASSEMBLE = "assemble"
    STAGE_DONE = "done"
    STAGE_CHOICES = [
        (STAGE_QUEUE, "صف مونتاژ"),
        (STAGE_ASSEMBLE, "در حال مونتاژ"),
        (STAGE_DONE, "آماده QC"),
    ]
    STAGE_ORDER = [STAGE_QUEUE, STAGE_ASSEMBLE, STAGE_DONE]

    code = models.CharField("کد کار مونتاژ", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_assembly_jobs",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    assembly_name = models.CharField("شرح مونتاژ", max_length=150, blank=True, default="")
    stage = models.CharField("مرحله", max_length=20, choices=STAGE_CHOICES, default=STAGE_QUEUE)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    notes_log = models.JSONField("لاگ", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "کار مونتاژ"
        verbose_name_plural = "کارهای مونتاژ"

    def __str__(self):
        return self.code


class BetaClearanceJob(SoftDeleteModel):
    STAGE_QUEUE = "queue"
    STAGE_CHECK = "check"
    STAGE_RELEASED = "released"
    STAGE_CHOICES = [
        (STAGE_QUEUE, "صف ترخیص"),
        (STAGE_CHECK, "بررسی خروج"),
        (STAGE_RELEASED, "ترخیص‌شده"),
    ]
    STAGE_ORDER = [STAGE_QUEUE, STAGE_CHECK, STAGE_RELEASED]

    code = models.CharField("کد ترخیص", max_length=40, unique=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beta_clearance_jobs",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    destination = models.CharField("مقصد", max_length=40, blank=True, default="")
    stage = models.CharField("مرحله", max_length=20, choices=STAGE_CHOICES, default=STAGE_QUEUE)
    progress = models.PositiveIntegerField("پیشرفت", default=0)
    notes_log = models.JSONField("لاگ", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "کار ترخیص"
        verbose_name_plural = "کارهای ترخیص"

    def __str__(self):
        return self.code
