"""Customer wallet and retained SMS/engagement models."""

from datetime import time
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from .base import AppendOnlyModel, MONEY_KWARGS, ReferenceCodeModel
from .config import SmsStatus, SmsType
from .people import Customer, LoyaltyLevel


class WalletTransaction(AppendOnlyModel):
    TYPE_CHOICES = [
        ("deposit", "واریز"),
        ("withdraw", "برداشت"),
        ("sale", "پرداخت فروش"),
        ("refund", "بازگشت"),
        ("adjustment", "اصلاح"),
    ]
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="wallet_transactions"
    )
    amount = models.DecimalField(**MONEY_KWARGS)
    transaction_type = models.CharField(
        max_length=12, choices=TYPE_CHOICES, default="adjustment"
    )
    description = models.CharField(max_length=255, blank=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="wallet_transactions",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(amount=0), name="ck_wallet_amount_nonzero"),
        ]
        indexes = [
            models.Index(fields=["customer", "created_at"], name="ix_wallet_customer_date"),
        ]

    @property
    def balance_after(self):
        if not self.pk:
            return None
        return (
            WalletTransaction.objects.filter(
                customer=self.customer,
                created_at__lte=self.created_at,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )


class SMSLog(ReferenceCodeModel):
    reference_code_fields = {
        "sms_type": "sms_type_ref",
        "status": "status_ref",
    }
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
        Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_logs"
    )
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    sms_type_ref = models.ForeignKey(
        SmsType, db_column="sms_type", default="manual", on_delete=models.PROTECT
    )
    status_ref = models.ForeignKey(
        SmsStatus, db_column="status", default="pending", on_delete=models.PROTECT
    )
    provider_response = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_logs",
    )

    class Meta:
        ordering = ["-created_at"]

    sms_type = property(
        lambda self: self.reference_code("sms_type"),
        lambda self, value: self.set_reference_code("sms_type", value),
    )
    status = property(
        lambda self: self.reference_code("status"),
        lambda self, value: self.set_reference_code("status", value),
    )

    def get_sms_type_display(self):
        return self.reference_label("sms_type")

    def get_status_display(self):
        return self.reference_label("status")


class BirthdaySmsSettings(models.Model):
    is_enabled = models.BooleanField(default=False)
    message_template = models.TextField(
        default="تولدت مبارک {name}! از طرف {shop_name} بهترین‌ها را برایت آرزومندیم."
    )
    shop_name = models.CharField(max_length=100, default="سام اکسون")
    send_time = models.TimeField(default=time(10, 0))
    last_run_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BirthdaySmsExclusion(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="birthday_sms_exclusions"
    )
    exclude_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "exclude_date"], name="uq_birthday_exclusion"
            ),
        ]


class SmsClubSettings(models.Model):
    DISCOUNT_TYPE_CHOICES = [("amount", "مبلغ ثابت"), ("percent", "درصد")]
    shop_name = models.CharField(max_length=100, default="سام اکسون")
    auto_order_placed = models.BooleanField(default=True)
    auto_welcome = models.BooleanField(default=True)
    auto_level_up = models.BooleanField(default=True)
    order_placed_template = models.TextField(
        default="{name} عزیز، سفارش شما به مبلغ {amount} ریال ثبت شد. {shop_name}"
    )
    welcome_template = models.TextField(
        default="{name} عزیز، به باشگاه {shop_name} خوش آمدید! کد عضویت شما: {code}"
    )
    level_up_template = models.TextField(
        default="{name} عزیز، سطح باشگاه شما به «{level}» ارتقا یافت. {shop_name}"
    )
    discount_template = models.TextField(
        default="{name} عزیز! تخفیف ویژه {discount_label} از {shop_name} — منتظر دیدار شما هستیم."
    )
    default_discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="amount"
    )
    default_discount_value = models.DecimalField(default=0, **MONEY_KWARGS)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ReminderCampaign(models.Model):
    name = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    interval_months = models.PositiveIntegerField(default=3)
    message_template = models.TextField(
        default="{name} عزیز، {shop_name} دلتنگ شماست! کد باشگاه: {code} — سطح: {level}"
    )
    shop_name = models.CharField(max_length=100, default="سام اکسون")
    loyalty_levels = models.ManyToManyField(
        LoyaltyLevel, blank=True, related_name="reminder_campaigns"
    )
    min_months_since_purchase = models.PositiveIntegerField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class ReminderSendLog(models.Model):
    pk = models.CompositePrimaryKey("campaign", "customer", "period_key")
    campaign = models.ForeignKey(
        ReminderCampaign, on_delete=models.CASCADE, related_name="send_logs"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="reminder_logs"
    )
    period_key = models.CharField(max_length=20)
    sent_at = models.DateTimeField(auto_now_add=True)

