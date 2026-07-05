"""Tests for business data reset."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from auth import roles
from backend.models import Customer, Sale
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
        Sale.objects.create(
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

    def test_clears_business_data(self):
        reset_business_data()
        self.assertEqual(Customer.all_objects.count(), 0)
        self.assertEqual(Sale.all_objects.count(), 0)

    def test_admin_user_ids_includes_superuser_and_admin_role(self):
        superuser = User.objects.create_superuser(username="su", password="testpass123")
        ids = admin_user_ids()
        self.assertIn(self.admin.id, ids)
        self.assertIn(superuser.id, ids)
        self.assertNotIn(self.operator.id, ids)
