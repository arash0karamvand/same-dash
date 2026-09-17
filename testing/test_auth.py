"""تست نقش‌ها، مجوزها و همگام‌سازی superuser."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

import json

from auth import roles
from auth.permissions import (
    ALL_PERMISSIONS,
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
    get_user_extra_permissions,
    has_permission,
    is_system_admin,
    sanitize_role_permissions,
    sanitize_user_extra_permissions,
)
from backend.models import RoleDefinition, UserAccessProfile
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

    def test_user_extra_permissions_add_to_role(self):
        ensure_test_role(
            roles.OPERATOR,
            ["view_dashboard", "self_check_in"],
            label="فروشنده",
        )
        user = User.objects.create_user(username="op2", password="secret123")
        roles.assign_role(user, roles.OPERATOR)
        self.assertFalse(has_permission(user, VIEW_CUSTOMERS))
        UserAccessProfile.objects.create(
            user=user,
            extra_permissions=sanitize_user_extra_permissions([VIEW_CUSTOMERS, MANAGE_ROLES]),
        )
        self.assertTrue(has_permission(user, VIEW_CUSTOMERS))
        self.assertFalse(has_permission(user, MANAGE_ROLES))
        self.assertEqual(get_user_extra_permissions(user), {VIEW_CUSTOMERS})

    def test_builtin_role_edits_survive_seed(self):
        rd = RoleDefinition.objects.get(slug=roles.SALES_EXPERT)
        edited = [VIEW_DASHBOARD, VIEW_SALES, CREATE_SALE]
        rd.label = "کارشناس فروش ویرایش‌شده"
        rd.permissions = edited
        rd.save()

        seed_builtin_roles()

        rd.refresh_from_db()
        self.assertEqual(rd.label, "کارشناس فروش ویرایش‌شده")
        self.assertEqual(set(rd.permissions), set(edited))

    def test_locked_roles_stay_full_access_after_seed(self):
        rd = RoleDefinition.objects.get(slug=roles.ADMIN)
        rd.permissions = [VIEW_DASHBOARD]
        rd.save()

        seed_builtin_roles()

        rd.refresh_from_db()
        self.assertTrue(rd.grants_full_access)
        self.assertTrue(rd.is_locked)
        self.assertEqual(set(rd.permissions), set(ALL_PERMISSIONS))

    def test_missing_builtin_role_is_recreated(self):
        RoleDefinition.objects.filter(slug=roles.SALES_EXPERT).delete()
        self.assertFalse(RoleDefinition.objects.filter(slug=roles.SALES_EXPERT).exists())

        seed_builtin_roles()

        rd = RoleDefinition.objects.get(slug=roles.SALES_EXPERT)
        self.assertTrue(rd.is_builtin)
        self.assertIn(VIEW_DASHBOARD, rd.permissions)
        self.assertEqual(rd.department, "shop")


class UserDepartmentTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
        self.admin = User.objects.create_user(username="deptadm", password="secret123")
        roles.assign_role(self.admin, roles.ADMIN)
        self.client = Client()
        self.client.login(username="deptadm", password="secret123")

    def _create(self, username, role, branch=None):
        from auth.views import apply_user_access

        user = User.objects.create_user(username=username, password="secret123")
        apply_user_access(user, role, branch)
        return user

    def test_builtin_roles_have_departments(self):
        mapping = {
            roles.CEO: "managers",
            roles.ADMIN: "managers",
            roles.CO_CEO: "managers",
            roles.BRANCH_SUPERVISOR: "shop",
            roles.SALES_EXPERT: "shop",
            roles.ACCOUNTING_FINANCE: "office",
            roles.FACTORY_SUPERVISOR: "factory",
            roles.FREIGHT_SUPERVISOR: "factory",
        }
        for slug, department in mapping.items():
            self.assertEqual(RoleDefinition.objects.get(slug=slug).department, department)

    def test_user_dict_includes_primary_department(self):
        from auth.views import user_to_dict

        expert = self._create("dexpert", roles.SALES_EXPERT, "branch_1")
        payload = user_to_dict(expert)
        self.assertEqual(payload["primary_department"], "shop")
        self.assertEqual(payload["department_label"], "فروشگاه")

    def test_replace_clears_extras_and_assigns_role(self):
        from auth.views import set_user_extra_permissions

        expert = self._create("dcut", roles.SALES_EXPERT, "branch_1")
        set_user_extra_permissions(expert, [VIEW_ACCOUNTING, VIEW_CUSTOMERS])
        resp = self.client.post(
            f"/api/auth/users/{expert.id}/assign-department/",
            data=json.dumps({
                "department": "office",
                "mode": "replace",
                "role": roles.ACCOUNTING_FINANCE,
            }),
            content_type="application/json",
        )
        body = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200, msg=body)
        self.assertEqual(body["data"]["primary_department"], "office")
        self.assertEqual(body["data"]["role"], roles.ACCOUNTING_FINANCE)
        self.assertEqual(body["data"]["extra_permissions"], [])

    def test_keep_preserves_other_extras_and_requires_selection(self):
        from auth.views import set_user_extra_permissions

        expert = self._create("dkeep", roles.SALES_EXPERT, "branch_1")
        set_user_extra_permissions(expert, [VIEW_ACCOUNTING, CREATE_SALE])
        empty = self.client.post(
            f"/api/auth/users/{expert.id}/assign-department/",
            data=json.dumps({
                "department": "office",
                "mode": "keep",
                "selected_permissions": [],
            }),
            content_type="application/json",
        )
        empty_body = json.loads(empty.content)
        self.assertEqual(empty.status_code, 400)
        self.assertIn("یکی", empty_body.get("error") or "")

        kept = self.client.post(
            f"/api/auth/users/{expert.id}/assign-department/",
            data=json.dumps({
                "department": "office",
                "mode": "keep",
                "selected_permissions": [VIEW_ACCOUNTING],
            }),
            content_type="application/json",
        )
        body = json.loads(kept.content)
        self.assertEqual(kept.status_code, 200, msg=body)
        self.assertEqual(body["data"]["primary_department"], "office")
        self.assertEqual(body["data"]["role"], roles.SALES_EXPERT)
        self.assertIn(VIEW_ACCOUNTING, body["data"]["extra_permissions"])
        self.assertIn(CREATE_SALE, body["data"]["extra_permissions"])

    def test_full_access_cannot_leave_managers(self):
        ceo = self._create("dceo", roles.CEO)
        resp = self.client.post(
            f"/api/auth/users/{ceo.id}/assign-department/",
            data=json.dumps({
                "department": "shop",
                "mode": "keep",
                "selected_permissions": [VIEW_CUSTOMERS],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

