"""مدل‌های بخش‌بندی RFM مشتریان — تنظیمات، بخش‌ها، کش امتیاز و لاگ اکشن."""

from django.conf import settings
from django.db import models
from django.db.models import Sum

from .base import AppendOnlyModel, MONEY_KWARGS
from .people import Customer

PERCENT_KWARGS = {"max_digits": 6, "decimal_places": 2}


def default_r_thresholds():
    return [
        {"max_days": 90, "score": 5},
        {"max_days": 180, "score": 4},
        {"max_days": 365, "score": 3},
        {"max_days": 730, "score": 2},
        {"max_days": 99999, "score": 1},
    ]


def default_f_thresholds():
    return [
        {"min_count": 5, "score": 5},
        {"min_count": 4, "score": 4},
        {"min_count": 3, "score": 3},
        {"min_count": 2, "score": 2},
        {"min_count": 1, "score": 1},
    ]


def default_m_thresholds():
    return [
        {"min_amount": 500_000_000, "score": 5},
        {"min_amount": 200_000_000, "score": 4},
        {"min_amount": 80_000_000, "score": 3},
        {"min_amount": 30_000_000, "score": 2},
        {"min_amount": 0, "score": 1},
    ]


class RfmSettings(models.Model):
    SCORE_METHOD_QUANTILE = "quantile"
    SCORE_METHOD_THRESHOLD = "threshold"
    SCORE_METHOD_CHOICES = [
        (SCORE_METHOD_QUANTILE, "پنجک (۱ تا ۵)"),
        (SCORE_METHOD_THRESHOLD, "آستانهٔ دستی"),
    ]
    MONETARY_FINAL = "final_amount"
    MONETARY_PAID = "paid_amount"
    MONETARY_CHOICES = [
        (MONETARY_FINAL, "مبلغ نهایی فاکتور"),
        (MONETARY_PAID, "مبلغ پرداخت‌شده"),
    ]
    WINDOW_LOOKBACK = "lookback"
    WINDOW_LIFETIME = "lifetime"
    WINDOW_CHOICES = [
        (WINDOW_LOOKBACK, "بازهٔ انتخاب‌شده"),
        (WINDOW_LIFETIME, "کل طول عمر مشتری"),
    ]

    lookback_days = models.PositiveIntegerField(default=730)
    score_method = models.CharField(
        max_length=16, choices=SCORE_METHOD_CHOICES, default=SCORE_METHOD_QUANTILE
    )
    quantile_count = models.PositiveSmallIntegerField(default=5)
    monetary_field = models.CharField(
        max_length=16, choices=MONETARY_CHOICES, default=MONETARY_FINAL
    )
    fm_window = models.CharField(
        max_length=16, choices=WINDOW_CHOICES, default=WINDOW_LOOKBACK
    )
    r_thresholds = models.JSONField(default=default_r_thresholds)
    f_thresholds = models.JSONField(default=default_f_thresholds)
    m_thresholds = models.JSONField(default=default_m_thresholds)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_stats = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RfmSegment(models.Model):
    ACTION_PLAYBOOK = "playbook"
    ACTION_CALL = "call"
    ACTION_SMS = "sms"
    ACTION_VIP = "vip"
    ACTION_SEGMENT_CHANGE = "segment_change"
    ACTION_CHOICES = [
        (ACTION_PLAYBOOK, "نمایش راهنما"),
        (ACTION_CALL, "تماس فروش"),
        (ACTION_SMS, "پیامک"),
        (ACTION_VIP, "دعوت VIP"),
    ]

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=40, unique=True)
    color = models.CharField(max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    r_scores = models.JSONField(default=list)
    f_scores = models.JSONField(default=list)
    m_scores = models.JSONField(default=list)
    action_type = models.CharField(
        max_length=16, choices=ACTION_CHOICES, default=ACTION_PLAYBOOK
    )
    action_title = models.CharField(max_length=160, blank=True)
    action_body = models.TextField(blank=True)
    no_discount = models.BooleanField(default=False)
    auto_sms = models.BooleanField(default=False)
    sms_template = models.TextField(blank=True)
    sms_cooldown_days = models.PositiveIntegerField(default=90)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class CustomerRfmScore(models.Model):
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="rfm_score"
    )
    r_raw = models.PositiveIntegerField(default=0)
    f_raw = models.PositiveIntegerField(default=0)
    m_raw = models.DecimalField(default=0, **MONEY_KWARGS)
    r_score = models.PositiveSmallIntegerField(default=1)
    f_score = models.PositiveSmallIntegerField(default=1)
    m_score = models.PositiveSmallIntegerField(default=1)
    rfm_code = models.CharField(max_length=3, db_index=True)
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    segment = models.ForeignKey(
        RfmSegment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customer_scores",
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["segment", "rfm_code"], name="ix_rfm_segment_code"),
        ]

    def __str__(self):
        return f"{self.customer_id}:{self.rfm_code}"


class CashbackProgram(models.Model):
    REDEEM_AUTO = "auto_each_sale"
    REDEEM_WALLET = "wallet_credit"
    REDEEM_MANUAL = "manual"
    REDEEM_CHOICES = [
        (REDEEM_AUTO, "هر فاکتور از مبلغ کم شود"),
        (REDEEM_WALLET, "شارژ یک‌باره کیف پول"),
        (REDEEM_MANUAL, "بدون مصرف خودکار"),
    ]

    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    earn_percent = models.DecimalField(default=0, **PERCENT_KWARGS)
    base_usable_percent = models.DecimalField(default=100, **PERCENT_KWARGS)
    redeem_mode = models.CharField(
        max_length=20, choices=REDEEM_CHOICES, default=REDEEM_MANUAL
    )
    segments = models.ManyToManyField(
        RfmSegment, blank=True, related_name="cashback_programs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class CashbackUnlockStep(models.Model):
    program = models.ForeignKey(
        CashbackProgram, on_delete=models.CASCADE, related_name="unlock_steps"
    )
    extra_purchase_percent = models.DecimalField(**PERCENT_KWARGS)
    extra_usable_percent = models.DecimalField(**PERCENT_KWARGS)

    class Meta:
        ordering = ["extra_purchase_percent", "id"]

    def __str__(self):
        return f"{self.program_id}:{self.extra_purchase_percent}"


class CashbackTransaction(AppendOnlyModel):
    TYPE_EARN = "earn"
    TYPE_SPEND = "spend"
    TYPE_WALLET = "wallet_credit"
    TYPE_REVERSAL = "reversal"
    TYPE_CHOICES = [
        (TYPE_EARN, "کسب"),
        (TYPE_SPEND, "مصرف روی فاکتور"),
        (TYPE_WALLET, "شارژ کیف پول"),
        (TYPE_REVERSAL, "برگشت"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="cashback_transactions"
    )
    program = models.ForeignKey(
        CashbackProgram,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    amount = models.DecimalField(**MONEY_KWARGS)
    transaction_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cashback_transactions",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cashback_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount=0), name="ck_cashback_amount_nonzero"
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "created_at"], name="ix_cashback_customer_date"),
            models.Index(fields=["sale", "transaction_type"], name="ix_cashback_sale_type"),
        ]

    @property
    def balance_after(self):
        if not self.pk:
            return None
        return (
            CashbackTransaction.objects.filter(
                customer=self.customer,
                created_at__lte=self.created_at,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )


class RfmActionLog(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="rfm_action_logs"
    )
    segment = models.ForeignKey(
        RfmSegment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_logs",
    )
    previous_segment = models.ForeignKey(
        RfmSegment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="previous_action_logs",
    )
    action_type = models.CharField(max_length=16, default=RfmSegment.ACTION_SMS)
    sms_log = models.ForeignKey(
        "backend.SMSLog",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rfm_action_logs",
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(
                fields=["customer", "action_type", "sent_at"],
                name="ix_rfm_action_customer",
            ),
        ]
