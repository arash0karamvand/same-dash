"""ثبت مدل‌ها در پنل مدیریت Django برای مدیریت سریع داده‌ها.

نکته مهم: بازه هر سطح باشگاه (حداقل/حداکثر خرید) در همین پنل توسط مدیر
تعیین می‌شود و هیچ مقدار ثابتی در کد وجود ندارد.
"""

from django.contrib import admin

from .models import (
    Account,
    AccountingEntry,
    AuditLog,
    Customer,
    CustomerLevelHistory,
    DetailedAccount,
    LoyaltyLevel,
    Product,
    Sale,
    SaleInstallment,
    SaleLineItem,
    Seller,
    SMSLog,
    StaffAttendance,
    StaffProfile,
    SubsidiaryAccount,
)


@admin.register(LoyaltyLevel)
class LoyaltyLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "min_purchase", "max_purchase", "discount_percent", "points", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_editable = ("min_purchase", "max_purchase", "discount_percent", "points", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "level", "total_purchases", "last_purchase_at", "is_active")
    list_filter = ("level", "is_active")
    search_fields = ("full_name", "phone", "email")
    readonly_fields = ("total_purchases", "last_purchase_at", "level", "joined_at", "updated_at")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer",
        "amount",
        "discount",
        "final_amount",
        "paid_amount",
        "payment_status",
        "sold_at",
    )
    list_filter = ("payment_status", "payment_method", "sold_at")
    search_fields = ("invoice_number", "customer__full_name", "customer__phone")
    readonly_fields = ("recorded_by", "created_at")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "slug", "account_class", "normal_balance", "sort_order", "is_active")
    list_filter = ("account_class", "is_active")
    search_fields = ("name", "slug", "code")
    ordering = ("sort_order", "name")


@admin.register(SubsidiaryAccount)
class SubsidiaryAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account", "is_active")
    list_filter = ("account__account_class", "is_active")
    search_fields = ("name", "code", "account__name")


@admin.register(DetailedAccount)
class DetailedAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "subsidiary", "is_active")
    search_fields = ("name", "code", "subsidiary__name")


@admin.register(AccountingEntry)
class AccountingEntryAdmin(admin.ModelAdmin):
    list_display = ("document_number", "entry_type", "account", "debit", "credit", "entry_date", "is_approved")
    list_filter = ("entry_type", "account__account_class", "is_approved")
    search_fields = ("description",)
    list_editable = ("is_approved",)


@admin.register(CustomerLevelHistory)
class CustomerLevelHistoryAdmin(admin.ModelAdmin):
    list_display = ("customer", "previous_level", "new_level", "total_purchases_at_change", "changed_at")
    search_fields = ("customer__full_name",)
    readonly_fields = ("customer", "previous_level", "new_level", "total_purchases_at_change", "changed_at", "reason")


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "customer", "sms_type", "status", "created_by", "created_at", "sent_at")
    list_filter = ("status", "sms_type")
    search_fields = ("phone_number", "message")
    readonly_fields = ("created_at", "sent_at", "provider_response", "error_message")


@admin.register(SaleInstallment)
class SaleInstallmentAdmin(admin.ModelAdmin):
    list_display = ("sale", "amount", "due_date", "payment_method", "status", "check_number")
    list_filter = ("status", "payment_method")


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "branch", "phone", "is_active")
    list_filter = ("branch", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "default_price", "is_active")


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "branch")
    list_filter = ("branch",)


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ("seller", "date", "status", "approval_status", "recorded_by")
    list_filter = ("status", "approval_status", "date")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "message", "is_executive_only")
    list_filter = ("action", "is_executive_only")
