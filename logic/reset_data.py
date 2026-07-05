"""پاک‌سازی همه داده‌های عملیاتی — کاربران مدیر سیستم حفظ می‌شوند."""

from django.contrib.auth import get_user_model
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
    LoyaltyLevel,
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
    WalletTransaction,
)

User = get_user_model()


def admin_user_ids():
    """شناسه کاربرانی که باید حفظ شوند (superuser یا نقش admin)."""
    ids = set(User.objects.filter(is_superuser=True).values_list("pk", flat=True))
    for user in User.objects.only("id").iterator():
        if roles.get_user_role(user) == ADMIN:
            ids.add(user.id)
    return ids


def reset_business_data():
    """
    حذف همه داده‌های ذخیره‌شده به جز کاربران مدیر سیستم.
    تعاریف نقش (RoleDefinition) حفظ می‌شوند.
    """
    keep_ids = admin_user_ids()
    counts = {}

    with transaction.atomic():
        counts["reminder_send_logs"] = ReminderSendLog.objects.all().delete()[0]
        counts["wallet_transactions"] = WalletTransaction.objects.all().delete()[0]
        counts["sale_line_items"] = SaleLineItem.objects.all().delete()[0]
        counts["sale_installments"] = SaleInstallment.all_objects.all().delete()[0]
        counts["accounting_entries"] = AccountingEntry.objects.all().delete()[0]
        counts["sales"] = Sale.all_objects.all().delete()[0]
        counts["customer_level_history"] = CustomerLevelHistory.objects.all().delete()[0]
        counts["birthday_sms_exclusions"] = BirthdaySmsExclusion.objects.all().delete()[0]
        counts["customers"] = Customer.all_objects.all().delete()[0]
        counts["sms_logs"] = SMSLog.objects.all().delete()[0]
        counts["audit_logs"] = AuditLog.objects.all().delete()[0]
        counts["staff_attendance"] = StaffAttendance.all_objects.all().delete()[0]
        counts["sellers"] = Seller.all_objects.all().delete()[0]
        counts["products"] = Product.all_objects.all().delete()[0]
        counts["product_categories"] = ProductCategory.all_objects.all().delete()[0]
        counts["loyalty_levels"] = LoyaltyLevel.all_objects.all().delete()[0]
        counts["reminder_campaigns"] = ReminderCampaign.objects.all().delete()[0]
        counts["org_ranks"] = OrgRank.objects.all().delete()[0]

        BirthdaySmsSettings.objects.all().delete()
        BirthdaySmsSettings.get_solo()
        SmsClubSettings.objects.all().delete()
        SmsClubSettings.get_solo()

        counts["users_deleted"] = User.objects.exclude(pk__in=keep_ids).delete()[0]
        counts["admin_users_kept"] = len(keep_ids)

    return counts
