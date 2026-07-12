"""تست نقش‌ها، مجوزها و همگام‌سازی superuser."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from auth import roles
from auth.permissions import (
    CREATE_ACCOUNTING,
    CREATE_SALE,
    DELETE_CUSTOMER,
    EDIT_ACCOUNTING,
    MANAGE_LOYALTY,
    MANAGE_ROLES,
    RESET_BUSINESS_DATA,
    SELF_CHECK_IN,
    VIEW_ACCOUNTING,
    VIEW_CUSTOMERS,
    VIEW_DASHBOARD,
    VIEW_SALES,
    has_permission,
    is_system_admin,
    sanitize_role_permissions,
)
from backend.models import RoleDefinition
from logic.role_definitions import seed_builtin_roles
from testing.role_helpers import ACCOUNTANT_PERMISSIONS, ensure_test_role

User = get_user_model()


class RolePermissionTest(TestCase):
    def setUp(self):
        seed_builtin_roles()

    def test_admin_has_all_permissions(self):
        user = User.objects.create_user(username="adm", password="secret123")
        roles.assign_role(user, roles.ADMIN)
        self.assertTrue(has_permission(user, DELETE_CUSTOMER))
        self.assertTrue(has_permission(user, MANAGE_LOYALTY))
        self.assertTrue(has_permission(user, RESET_BUSINESS_DATA))
        self.assertTrue(is_system_admin(user))

    def test_custom_accountant_permissions(self):
        ensure_test_role("accountant", ACCOUNTANT_PERMISSIONS, label="حسابدار", needs_branch=True)
        user = User.objects.create_user(username="acc", password="secret123")
        roles.assign_role(user, "accountant")
        self.assertTrue(has_permission(user, VIEW_SALES))
        self.assertTrue(has_permission(user, CREATE_ACCOUNTING))
        self.assertTrue(has_permission(user, EDIT_ACCOUNTING))
        self.assertFalse(has_permission(user, DELETE_CUSTOMER))
        self.assertFalse(has_permission(user, MANAGE_LOYALTY))
        self.assertFalse(has_permission(user, MANAGE_ROLES))
        self.assertTrue(has_permission(user, VIEW_DASHBOARD))

    def test_custom_sales_manager_permissions(self):
        ensure_test_role(
            roles.SALES_MANAGER,
            ["view_customers", "manage_loyalty", "view_dashboard"],
            label="مدیر فروش",
        )
        user = User.objects.create_user(username="sm", password="secret123")
        roles.assign_role(user, roles.SALES_MANAGER)
        self.assertTrue(has_permission(user, MANAGE_LOYALTY))
        self.assertTrue(has_permission(user, VIEW_DASHBOARD))

    def test_custom_operator_limited(self):
        ensure_test_role(
            roles.OPERATOR,
            ["view_dashboard", "self_check_in"],
            label="فروشنده",
        )
        user = User.objects.create_user(username="op", password="secret123")
        roles.assign_role(user, roles.OPERATOR)
        self.assertFalse(has_permission(user, DELETE_CUSTOMER))
        self.assertTrue(has_permission(user, VIEW_DASHBOARD))
        self.assertTrue(has_permission(user, SELF_CHECK_IN))

    def test_pending_has_no_permissions(self):
        user = User.objects.create_user(username="p", password="secret123")
        roles.assign_role(user, roles.PENDING)
        self.assertFalse(has_permission(user, VIEW_SALES))

    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser(username="su", password="secret123", email="")
        self.assertEqual(roles.get_user_role(user), roles.ADMIN)
        self.assertTrue(is_system_admin(user))

    def test_sanitize_strips_admin_only_permissions(self):
        cleaned = sanitize_role_permissions(
            "custom_role",
            ["view_sales", MANAGE_ROLES, RESET_BUSINESS_DATA],
        )
        self.assertIn("view_sales", cleaned)
        self.assertNotIn(MANAGE_ROLES, cleaned)
        self.assertNotIn(RESET_BUSINESS_DATA, cleaned)

    def test_admin_role_always_gets_all_permissions(self):
        cleaned = sanitize_role_permissions(roles.ADMIN, ["view_sales"])
        self.assertIn(MANAGE_ROLES, cleaned)
        self.assertIn(RESET_BUSINESS_DATA, cleaned)

    def test_custom_role_cannot_keep_manage_roles(self):
        rd = RoleDefinition.objects.create(
            slug="supervisor",
            label="سرپرست",
            permissions=[MANAGE_ROLES, "view_customers"],
            is_builtin=False,
        )
        seed_builtin_roles()
        rd.refresh_from_db()
        self.assertNotIn(MANAGE_ROLES, rd.permissions)
        self.assertIn("view_customers", rd.permissions)

    def test_org_builtin_roles_seeded(self):
        seed_builtin_roles()
        slugs = set(
            RoleDefinition.objects.filter(is_builtin=True).values_list("slug", flat=True)
        )
        self.assertIn(roles.ADMIN, slugs)
        self.assertIn(roles.CEO, slugs)
        self.assertIn(roles.CO_CEO, slugs)
        self.assertIn(roles.BRANCH_SUPERVISOR, slugs)
        self.assertIn(roles.ACCOUNTING_FINANCE, slugs)
        self.assertIn(roles.SALES_EXPERT, slugs)

    def test_ceo_has_full_permissions(self):
        user = User.objects.create_user(username="ceo_user", password="secret123")
        roles.assign_role(user, roles.CEO)
        self.assertTrue(has_permission(user, DELETE_CUSTOMER))
        self.assertTrue(has_permission(user, MANAGE_ROLES))

    def test_co_ceo_accounting_only_by_default(self):
        user = User.objects.create_user(username="coceo", password="secret123")
        roles.assign_role(user, roles.CO_CEO)
        self.assertTrue(has_permission(user, VIEW_ACCOUNTING))
        self.assertFalse(has_permission(user, CREATE_SALE))
        self.assertFalse(has_permission(user, VIEW_CUSTOMERS))
