"""کمک‌کننده‌های فروشنده."""

from auth.branches import DEFAULT_BRANCH
from auth.permissions import SELF_CHECK_IN, has_permission
from auth.roles import ADMIN, LEGACY_ROLES, PENDING, get_user_role
from backend.models import RoleDefinition, Seller, StaffAttendance, StaffProfile
from django.utils import timezone


def _staff_profile(user):
    """پروفایل شعبه کاربر — بدون خطا اگر وجود نداشته باشد."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.staff_profile
    except StaffProfile.DoesNotExist:
        return None


def role_needs_seller(user):
    """آیا این کاربر باید رکورد فروشنده (Seller) داشته باشد؟"""
    role = get_user_role(user)
    if role in (None, PENDING):
        return False
    if role == ADMIN or user.is_superuser:
        return True
    if has_permission(user, SELF_CHECK_IN):
        return True
    profile = _staff_profile(user)
    if profile:
        return True
    try:
        rd = RoleDefinition.objects.filter(slug=role).first()
        if rd and rd.needs_branch:
            return True
    except Exception:
        pass
    return role in LEGACY_ROLES


def ensure_seller_for_user(user, branch=None):
    """ایجاد یا به‌روزرسانی فروشنده متصل به حساب کاربر."""
    if not user or not user.is_authenticated:
        return None

    profile = _staff_profile(user)
    resolved_branch = branch or (profile.branch if profile else None) or DEFAULT_BRANCH
    name = user.get_full_name() or user.username

    seller = Seller.objects.filter(user=user, is_active=True).first()
    if not seller:
        inactive = Seller.objects.filter(user=user, is_active=False).first()
        if inactive:
            inactive.is_active = True
            inactive.full_name = name
            inactive.branch = resolved_branch
            inactive.save(update_fields=["is_active", "full_name", "branch"])
            return inactive

    if seller:
        updates = []
        if seller.full_name != name:
            seller.full_name = name
            updates.append("full_name")
        if resolved_branch and seller.branch != resolved_branch:
            seller.branch = resolved_branch
            updates.append("branch")
        if updates:
            seller.save(update_fields=updates)
        return seller

    return Seller.objects.create(full_name=name, branch=resolved_branch, user=user)


def get_seller_for_user(user):
    """فروشنده متصل به کاربر — در صورت نیاز خودکار ساخته می‌شود."""
    if not user or not user.is_authenticated:
        return None

    seller = Seller.objects.filter(user=user, is_active=True).first()
    if seller:
        return seller

    if not role_needs_seller(user):
        return None

    return ensure_seller_for_user(user)


def sync_seller_profiles():
    """همگام‌سازی Seller برای همه کاربران واجد شرایط (پس از تغییر نقش)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    synced = 0
    for user in User.objects.filter(is_active=True):
        if role_needs_seller(user) and not Seller.objects.filter(user=user, is_active=True).exists():
            ensure_seller_for_user(user)
            synced += 1
    return synced


def get_user_branch(user):
    seller = get_seller_for_user(user)
    if seller:
        return seller.branch
    profile = _staff_profile(user)
    return profile.branch if profile else None


def effective_sale_branch(user, today=None):
    """شعبه فعال: شعبه کاری تاییدشده امروز یا شعبه ثبت فروشنده."""
    seller = get_seller_for_user(user)
    if not seller:
        return get_user_branch(user)

    day = today or timezone.localdate()
    record = (
        StaffAttendance.objects.filter(
            seller=seller,
            date=day,
            approval_status="approved",
            status="present",
            check_out_at__isnull=True,
        )
        .order_by("-approved_at")
        .first()
    )
    if record:
        return record.work_branch or seller.branch
    return seller.branch
