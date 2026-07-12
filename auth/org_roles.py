"""قوانین نقش‌های سازمانی — خواندن از MySQL."""

from django.db.utils import OperationalError

from auth import roles
from auth.roles import get_user_role
from backend.models import RoleDefinition
from logic.sale_workflow import BRANCH_MASK_STAGES


def _get_role_def(slug):
    try:
        return RoleDefinition.objects.get(slug=slug)
    except (RoleDefinition.DoesNotExist, OperationalError):
        return None


def is_full_access_role(slug):
    try:
        rd = _get_role_def(slug)
        if rd and hasattr(rd, "grants_full_access"):
            return rd.grants_full_access
    except Exception:
        pass
    return slug in {roles.ADMIN, roles.CEO}


def is_locked_role(slug):
    try:
        rd = _get_role_def(slug)
        if rd and hasattr(rd, "is_locked"):
            return rd.is_locked
    except Exception:
        pass
    return slug in {roles.ADMIN, roles.CEO}


def _has_role(user, slug):
    return get_user_role(user) == slug


def is_branch_supervisor(user):
    return _has_role(user, roles.BRANCH_SUPERVISOR)


def is_sales_expert(user):
    return _has_role(user, roles.SALES_EXPERT)


def is_factory_supervisor(user):
    return _has_role(user, roles.FACTORY_SUPERVISOR)


def is_freight_supervisor(user):
    return _has_role(user, roles.FREIGHT_SUPERVISOR)


def is_accounting_finance(user):
    return _has_role(user, roles.ACCOUNTING_FINANCE)


def is_executive_user(user):
    """فقط مدیرعامل، معاون و مدیر سیستم — دسترسی کامل به همه سفارش‌ها."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in {roles.CEO, roles.CO_CEO, roles.ADMIN}


def should_mask_customer_for_sale(user, sale):
    """سرپرست شعبه پس از تایید/اصلاح، اطلاعات مشتری را نمی‌بیند."""
    if not is_branch_supervisor(user):
        return False
    return sale.workflow_stage in BRANCH_MASK_STAGES


def should_mask_prices_for_user(user):
    """کارخانه قیمت و مبالغ را نمی‌بیند."""
    return is_factory_supervisor(user)


def should_mask_amounts_for_user(user):
    """باربری مبالغ را نمی‌بیند (اطلاعات مشتری مجاز است)."""
    return is_freight_supervisor(user)


def sales_expert_summary_only(user):
    """کارشناس فروش فقط جمع فروش ماهانه — بدون لیست سفارش."""
    from auth.permissions import VIEW_OWN_SALES, VIEW_SALES, VIEW_SALES_SUMMARY, has_permission

    if not is_sales_expert(user):
        return False
    return (
        has_permission(user, VIEW_SALES_SUMMARY)
        and not has_permission(user, VIEW_OWN_SALES)
        and not has_permission(user, VIEW_SALES)
    )
