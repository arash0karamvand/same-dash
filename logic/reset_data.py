"""پاک‌سازی کامل داده‌ها — حذف فیزیکی (hard delete)؛ فقط مدیر سیستم حفظ می‌شود."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction

from auth import roles
from auth.roles import ADMIN
from backend.models import (
    AccountingEntry,
    AuditLog,
    BirthdaySmsExclusion,
    BirthdaySmsSettings,
    Customer,
    CustomerLevelHistory,
    FactoryAccountingEntry,
    FactoryDetailedAccount,
    FactoryOrder,
    FactoryOrderLineItem,
    FactorySubsidiaryAccount,
    LoyaltyLevel,
    OfficeOrder,
    OfficeOrderInstallment,
    OfficeOrderLineItem,
    OrgRank,
    Product,
    ProductCategory,
    ProductVariant,
    ReminderCampaign,
    ReminderSendLog,
    SMSLog,
    Sale,
    SaleInstallment,
    SaleLineItem,
    Seller,
    SmsClubSettings,
    StaffAttendance,
    StaffProfile,
    WalletTransaction,
)

User = get_user_model()


def admin_user_ids():
    """شناسه کاربرانی که باید حفظ شوند (superuser یا نقش مدیر سیستم)."""
    ids = set(User.objects.filter(is_superuser=True).values_list("pk", flat=True))
    for user in User.objects.only("id").iterator():
        if roles.get_user_role(user) == ADMIN:
            ids.add(user.id)
    return ids


def _hard_delete(qs):
    """حذف فیزیکی همه ردیف‌ها — بدون soft delete."""
    return qs.delete()[0]


def reset_business_data():
    """
    حذف فیزیکی همه داده‌های عملیاتی.
    فقط کاربران مدیر سیستم (و superuser) حفظ می‌شوند.
    تعاریف نقش، شعب، منو و lookupها حفظ می‌شوند.
    """
    keep_ids = admin_user_ids()
    counts = {}

    with transaction.atomic():
        # وابستگی‌های فروش و مالی — حذف فیزیکی حتی رکوردهای soft-deleted
        counts["reminder_send_logs"] = _hard_delete(ReminderSendLog.objects.all())
        counts["wallet_transactions"] = _hard_delete(WalletTransaction.objects.all())
        counts["factory_order_line_items"] = _hard_delete(FactoryOrderLineItem.objects.all())
        counts["factory_accounting_entries"] = _hard_delete(FactoryAccountingEntry.objects.all())
        counts["factory_orders"] = _hard_delete(FactoryOrder.all_objects.all())
        counts["office_order_installments"] = _hard_delete(OfficeOrderInstallment.all_objects.all())
        counts["office_order_line_items"] = _hard_delete(OfficeOrderLineItem.objects.all())
        counts["office_orders"] = _hard_delete(OfficeOrder.all_objects.all())
        counts["sale_line_items"] = _hard_delete(SaleLineItem.objects.all())
        counts["sale_installments"] = _hard_delete(SaleInstallment.all_objects.all())
        counts["accounting_entries"] = _hard_delete(AccountingEntry.objects.all())
        counts["factory_detailed_accounts"] = _hard_delete(FactoryDetailedAccount.objects.all())
        counts["factory_subsidiary_accounts"] = _hard_delete(FactorySubsidiaryAccount.objects.all())
        counts["sales"] = _hard_delete(Sale.all_objects.all())

        counts["customer_level_history"] = _hard_delete(CustomerLevelHistory.objects.all())
        counts["birthday_sms_exclusions"] = _hard_delete(BirthdaySmsExclusion.objects.all())
        counts["customers"] = _hard_delete(Customer.all_objects.all())

        counts["sms_logs"] = _hard_delete(SMSLog.objects.all())
        counts["audit_logs"] = _hard_delete(AuditLog.objects.all())
        counts["staff_attendance"] = _hard_delete(StaffAttendance.all_objects.all())
        counts["sellers"] = _hard_delete(Seller.all_objects.all())

        counts["product_variants"] = _hard_delete(ProductVariant.objects.all())
        counts["products"] = _hard_delete(Product.all_objects.all())
        counts["product_categories"] = _hard_delete(ProductCategory.all_objects.all())
        counts["loyalty_levels"] = _hard_delete(LoyaltyLevel.all_objects.all())
        counts["reminder_campaigns"] = _hard_delete(ReminderCampaign.objects.all())
        counts["org_ranks"] = _hard_delete(OrgRank.objects.all())

        # پروفایل پرسنل کاربران غیرمدیر
        counts["staff_profiles"] = _hard_delete(StaffProfile.objects.exclude(user_id__in=keep_ids))

        # تنظیمات پیامک به حالت اولیه
        BirthdaySmsSettings.objects.all().delete()
        BirthdaySmsSettings.get_solo()
        SmsClubSettings.objects.all().delete()
        SmsClubSettings.get_solo()

        # کاربران غیرمدیر — حذف فیزیکی
        counts["users_deleted"] = _hard_delete(User.objects.exclude(pk__in=keep_ids))
        counts["admin_users_kept"] = len(keep_ids)

        # نشست‌های کاربران حذف‌شده
        counts["sessions_cleared"] = _hard_delete(Session.objects.all())

    return counts
