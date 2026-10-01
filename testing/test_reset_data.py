"""Tests for business data reset — hard delete, keep system admin only."""

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from auth import roles
from backend.models import (
    Account,
    AuditCustomerTarget,
    AuditEvent,
    Branch,
    Customer,
    JournalEntry,
    Ledger,
    Material,
    Notification,
    OrgRank,
    RoleDefinition,
    Sale,
    StaffProfile,
    WalletTransaction,
    WorkflowStage,
)
from logic.accounting_documents import create_accounting_document
from logic.accounting_accounts import get_account
from logic.reset_data import admin_user_ids, reset_business_data
from testing.accounting_helpers import seed_accounts
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


class ResetBusinessDataTests(TransactionTestCase):
    def setUp(self):
        from logic.order_cycle import seed_workflow_stages
        from logic.seed_defaults import seed_system_defaults

        seed_system_defaults()
        seed_workflow_stages()
        for code, label, sort_order, is_terminal in (
            ("pending_branch", "صف فروشگاه", 0, False),
            ("branch_approved", "صف اداری", 1, False),
            ("accounting_approved", "ارسال به کارخانه", 2, False),
            ("in_production", "در حال ساخت", 3, False),
            ("production_done", "آماده باربری", 4, False),
            ("in_freight", "در باربری", 5, False),
            ("completed", "تکمیل شده", 6, True),
        ):
            WorkflowStage.objects.update_or_create(
                code=code,
                defaults={
                    "label": label,
                    "sort_order": sort_order,
                    "is_terminal": is_terminal,
                    "is_active": True,
                },
            )
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
        StaffProfile.objects.create(user=self.operator, branch_id="branch_1")
        reset_business_data()
        self.assertEqual(StaffProfile.objects.filter(user=self.operator).count(), 0)

    def test_admin_user_ids_includes_superuser_and_admin_role(self):
        superuser = User.objects.create_superuser(username="su", password="testpass123")
        ids = admin_user_ids()
        self.assertIn(self.admin.id, ids)
        self.assertIn(superuser.id, ids)
        self.assertNotIn(self.operator.id, ids)

    def test_hard_deletes_protected_posted_and_unlisted_rows(self):
        seed_accounts()
        bank = get_account("bank")
        revenue = get_account("other_revenue")
        create_accounting_document(
            lines=[
                {"account_id": bank.id, "debit": 100, "credit": 0, "description": "purge"},
                {"account_id": revenue.id, "debit": 0, "credit": 100, "description": "purge"},
            ],
            description="posted purge",
            is_approved=True,
        )
        self.assertTrue(JournalEntry.objects.filter(status=JournalEntry.STATUS_POSTED).exists())

        material = Material.objects.create(name="چوب تست")
        material.soft_delete()
        WalletTransaction.objects.create(
            customer=self.customer,
            amount=10,
            transaction_type="deposit",
            recorded_by=self.operator,
        )
        event = AuditEvent.objects.create(action="create", message="customer", user=self.operator)
        AuditCustomerTarget.objects.create(event=event, target=self.customer)
        Notification.objects.create(section=Notification.SECTION_SALES, title="یادآوری")
        rank = OrgRank.objects.create(name="رتبه تست")
        StaffProfile.objects.create(user=self.admin, org_rank=rank, manager=self.operator)

        reset_business_data(extra_keep_ids=(self.admin.pk,))

        self.assertEqual(Customer.all_objects.count(), 0)
        self.assertEqual(Sale.all_objects.count(), 0)
        self.assertEqual(Material.all_objects.count(), 0)
        self.assertEqual(WalletTransaction.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertEqual(AuditCustomerTarget.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Account.objects.count(), 0)
        self.assertEqual(OrgRank.objects.count(), 0)
        self.assertTrue(Ledger.objects.filter(code="office").exists())
        self.assertTrue(Branch.objects.exists())
        self.assertTrue(RoleDefinition.objects.filter(slug="admin").exists())
        self.assertTrue(User.objects.filter(username="admin1").exists())
        self.assertFalse(User.objects.filter(username="op1").exists())
        profile = StaffProfile.objects.get(user=self.admin)
        self.assertIsNone(profile.org_rank_id)
        self.assertIsNone(profile.manager_id)
