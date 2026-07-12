"""Tests for business data reset — hard delete, keep system admin only."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from auth import roles
from backend.models import Customer, Sale, StaffProfile
from logic.reset_data import admin_user_ids, reset_business_data
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


class ResetBusinessDataTests(TestCase):
    def setUp(self):
        ensure_legacy_test_roles()
        self.admin = User.objects.create_user(username="admin1", password="testpass123")
        roles.assign_role(self.admin, roles.ADMIN)

        self.operator = User.objects.create_user(username="op1", password="testpass123")
        roles.assign_role(self.operator, roles.OPERATOR)

        self.customer = Customer.objects.create(full_name="Test Customer", phone="09120000000")
        self.sale = Sale.objects.create(
            customer=self.customer,
            amount=1000,
            final_amount=1000,
            paid_amount=1000,
            recorded_by=self.operator,
        )

    def test_keeps_admin_users(self):
        reset_business_data()
        self.assertTrue(User.objects.filter(username="admin1").exists())
        self.assertFalse(User.objects.filter(username="op1").exists())

    def test_hard_deletes_business_data(self):
        # حتی رکورد soft-deleted هم باید فیزیکی پاک شود
        self.sale.soft_delete()
        self.customer.soft_delete()

        reset_business_data()

        self.assertEqual(Customer.all_objects.count(), 0)
        self.assertEqual(Sale.all_objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Sale.objects.count(), 0)

    def test_deletes_staff_profiles_of_non_admins(self):
        StaffProfile.objects.create(user=self.operator, branch="branch_1")
        reset_business_data()
        self.assertEqual(StaffProfile.objects.filter(user=self.operator).count(), 0)

    def test_admin_user_ids_includes_superuser_and_admin_role(self):
        superuser = User.objects.create_superuser(username="su", password="testpass123")
        ids = admin_user_ids()
        self.assertIn(self.admin.id, ids)
        self.assertIn(superuser.id, ids)
        self.assertNotIn(self.operator.id, ids)
