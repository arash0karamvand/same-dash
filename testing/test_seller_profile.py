"""تست خودکار ساخت پروفایل فروشنده."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from auth import roles
from auth.permissions import SELF_CHECK_IN, has_permission
from backend.models import RoleDefinition, Seller
from logic.role_definitions import sync_group_for_role
from logic.sellers import get_seller_for_user, role_needs_seller, sync_seller_profiles
from testing.role_helpers import ensure_test_role

User = get_user_model()


class SellerProfileTests(TestCase):
    def test_admin_gets_seller_even_when_builtin_needs_branch_false(self):
        roles.ensure_roles()
        admin_user = User.objects.create_user(username="adminseller", password="secret123")
        roles.assign_role(admin_user, roles.ADMIN)

        self.assertTrue(role_needs_seller(admin_user))
        seller = get_seller_for_user(admin_user)
        self.assertIsNotNone(seller)
        self.assertEqual(seller.user_id, admin_user.id)

    def test_custom_role_with_self_check_in_gets_seller(self):
        slug = "checkin_only"
        ensure_test_role(
            slug,
            [SELF_CHECK_IN, "view_dashboard"],
            label="checkin role",
            needs_branch=False,
        )
        user = User.objects.create_user(username="checkinuser", password="secret123")
        roles.assign_role(user, slug)

        self.assertTrue(has_permission(user, SELF_CHECK_IN))
        seller = get_seller_for_user(user)
        self.assertIsNotNone(seller)

    def test_sync_seller_profiles_backfills_missing(self):
        user = User.objects.create_user(username="syncme", password="secret123")
        roles.assign_role(user, roles.ADMIN)
        Seller.objects.filter(user=user).delete()

        self.assertEqual(sync_seller_profiles(), 1)
        self.assertTrue(Seller.objects.filter(user=user, is_active=True).exists())
