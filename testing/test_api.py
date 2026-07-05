"""تست endpointهای API، احراز هویت و کنترل سطح دسترسی."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import AccountingEntry, Customer, LoyaltyLevel, Sale, Seller
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def make_user(username, password="secret123", role=roles.OPERATOR):
    ensure_legacy_test_roles()
    user = User.objects.create_user(username=username, password=password)
    roles.assign_role(user, role)
    return user


def parse(response):
    return json.loads(response.content)


class AuthApiTest(TestCase):
    def test_login_me_logout(self):
        make_user("op1")
        client = Client()
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "op1", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["role"], roles.OPERATOR)

        resp = client.get("/api/auth/me/")
        self.assertTrue(parse(resp)["ok"])

        resp = client.post("/api/auth/logout/")
        self.assertTrue(parse(resp)["ok"])

    def test_public_register_forbidden(self):
        client = Client()
        resp = client.post(
            "/api/auth/users/",
            data=json.dumps({"username": "u1", "password": "secret123"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_admin_can_create_user(self):
        make_user("adm", role=roles.ADMIN)
        client = Client()
        client.login(username="adm", password="secret123")
        resp = client.post(
            "/api/auth/users/",
            data=json.dumps(
                {
                    "username": "newuser",
                    "password": "secret123",
                    "full_name": "New User",
                    "role": roles.OPERATOR,
                }
            ),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["user"]["role"], roles.OPERATOR)

    def test_login_invalid_credentials(self):
        make_user("op2")
        client = Client()
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "op2", "password": "wrong"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(body["ok"])


class AccessControlTest(TestCase):
    def test_anonymous_gets_401(self):
        resp = Client().get("/api/customers/")
        body = parse(resp)
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(body["ok"])

    def test_pending_forbidden(self):
        User.objects.create_user(username="p1", password="secret123")
        roles.assign_role(User.objects.get(username="p1"), roles.PENDING)
        client = Client()
        client.login(username="p1", password="secret123")
        resp = client.get("/api/customers/")
        self.assertEqual(resp.status_code, 403)

    def test_operator_cannot_manage_loyalty(self):
        make_user("op3", role=roles.OPERATOR)
        client = Client()
        client.login(username="op3", password="secret123")
        resp = client.post(
            "/api/loyalty-levels/",
            data=json.dumps({"name": "Gold", "min_purchase": 0}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_accountant_cannot_delete_customer(self):
        make_user("acc", role=roles.ACCOUNTANT)
        c = Customer.objects.create(full_name="X", phone="09120000099")
        client = Client()
        client.login(username="acc", password="secret123")
        resp = client.delete(f"/api/customers/{c.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_accountant_can_view_sales(self):
        make_user("acc2", role=roles.ACCOUNTANT)
        client = Client()
        client.login(username="acc2", password="secret123")
        resp = client.get("/api/sales/")
        self.assertTrue(parse(resp)["ok"])

    def test_operator_can_view_dashboard(self):
        make_user("op4", role=roles.OPERATOR)
        client = Client()
        client.login(username="op4", password="secret123")
        resp = client.get("/api/dashboard/summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(parse(resp)["ok"])


class CustomerApiTest(TestCase):
    def setUp(self):
        make_user("op", role=roles.OPERATOR)
        self.client = Client()
        self.client.login(username="op", password="secret123")

    def test_customer_create_and_no_delete(self):
        resp = self.client.post(
            "/api/customers/",
            data=json.dumps({"full_name": "Ali", "phone": "09120000010"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertTrue(body["ok"])
        cid = body["data"]["id"]

        resp = self.client.get("/api/customers/")
        self.assertEqual(len(parse(resp)["data"]["results"]), 1)

        resp = self.client.delete(f"/api/customers/{cid}/")
        self.assertEqual(resp.status_code, 403)


class SaleApiTest(TestCase):
    def setUp(self):
        LoyaltyLevel.objects.create(name="Bronze", min_purchase=0, max_purchase=10_000_000)
        self.op = make_user("op", role=roles.OPERATOR)
        make_user("op_other", role=roles.OPERATOR)
        self.customer = Customer.objects.create(full_name="Ali", phone="09120000011")
        self.client = Client()
        self.client.login(username="op", password="secret123")

    def test_record_paid_sale(self):
        resp = self.client.post(
            "/api/sales/",
            data=json.dumps(
                {"customer_id": self.customer.id, "amount": 1000000, "payment_status": "paid"}
            ),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.customer.refresh_from_db()
        self.assertEqual(int(self.customer.total_purchases), 1000000)
        self.assertEqual(AccountingEntry.objects.count(), 1)

    def test_operator_sees_only_own_sales(self):
        Sale.objects.create(
            customer=self.customer,
            amount=100,
            discount=0,
            final_amount=100,
            recorded_by=self.op,
        )
        other = User.objects.get(username="op_other")
        Sale.objects.create(
            customer=self.customer,
            amount=200,
            discount=0,
            final_amount=200,
            recorded_by=other,
        )
        resp = self.client.get("/api/sales/")
        results = parse(resp)["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["final_amount"], 100)


class SmsApiTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone="09120000012")
        make_user("sm", role=roles.SALES_MANAGER)
        make_user("op", role=roles.OPERATOR)
        self.sm_client = Client()
        self.sm_client.login(username="sm", password="secret123")
        self.op_client = Client()
        self.op_client.login(username="op", password="secret123")

    def test_sales_manager_can_send_sms(self):
        resp = self.sm_client.post(
            "/api/sms/send/",
            data=json.dumps({"customer_id": self.customer.id, "message": "سلام"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(body["ok"])
        self.assertIn("successful", body["data"])
        self.assertEqual(body["data"]["results"][0]["status"], "mock_sent")

    def test_operator_can_send_sms(self):
        resp = self.op_client.post(
            "/api/sms/send/",
            data=json.dumps({"customer_id": self.customer.id, "message": "سلام"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(body["ok"])

    def test_operator_can_view_sms_logs(self):
        resp = self.op_client.get("/api/sms/logs/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(parse(resp)["ok"])


class DashboardApiTest(TestCase):
    def setUp(self):
        make_user("sm", role=roles.SALES_MANAGER)
        self.client = Client()
        self.client.login(username="sm", password="secret123")

    def test_dashboard_summary(self):
        resp = self.client.get("/api/dashboard/summary/")
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertIn("customers_count", body["data"])
        self.assertIn("sales_today", body["data"])
        self.assertIn("jalali_day", body["data"]["sales_today"])


class StaffApiTest(TestCase):
    def setUp(self):
        self.seller = Seller.objects.create(full_name="Test Seller", branch="branch_1")
        make_user("adm", role=roles.ADMIN)
        make_user("sm", role=roles.SALES_MANAGER)
        self.admin = Client()
        self.admin.login(username="adm", password="secret123")
        self.manager = Client()
        self.manager.login(username="sm", password="secret123")

    def test_admin_can_delete_staff(self):
        resp = self.admin.delete(f"/api/staff/{self.seller.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(parse(resp)["ok"])
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.is_active)

    def test_sales_manager_cannot_delete_staff(self):
        resp = self.manager.delete(f"/api/staff/{self.seller.id}/")
        self.assertEqual(resp.status_code, 403)
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.is_active)


class AccountingApiTest(TestCase):
    def setUp(self):
        make_user("acc", role=roles.ACCOUNTANT)
        make_user("op", role=roles.OPERATOR)
        self.client = Client()
        self.client.login(username="acc", password="secret123")
        self.customer = Customer.objects.create(full_name="Ali", phone="09120000050")

    def _create_manual_entry(self, **overrides):
        payload = {
            "entry_type": "other",
            "credit": 500000,
            "description": "دریافت نقدی",
        }
        payload.update(overrides)
        return self.client.post(
            "/api/accounting/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_create_manual_entry(self):
        resp = self._create_manual_entry()
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["credit"], 500000)
        self.assertEqual(body["data"]["amount"], 500000)
        self.assertFalse(body["data"]["is_system"])

    def test_create_requires_description_and_amount(self):
        resp = self._create_manual_entry(description="")
        self.assertEqual(resp.status_code, 400)
        resp = self._create_manual_entry(credit=0)
        self.assertEqual(resp.status_code, 400)

    def test_create_all_entry_types(self):
        for entry_type, label in AccountingEntry.ENTRY_TYPE_CHOICES:
            resp = self._create_manual_entry(
                entry_type=entry_type, debit=1000, credit=0, description=f"سند {label}"
            )
            self.assertEqual(resp.status_code, 201, msg=entry_type)

    def test_create_debit_entry(self):
        resp = self._create_manual_entry(entry_type="adjustment", debit=300000, credit=0)
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(body["data"]["debit"], 300000)
        self.assertEqual(body["data"]["credit"], 0)
        self.assertEqual(body["data"]["amount"], 300000)

    def test_edit_and_delete_manual_entry(self):
        entry_id = parse(self._create_manual_entry())["data"]["id"]
        resp = self.client.put(
            f"/api/accounting/{entry_id}/",
            data=json.dumps({"credit": 700000, "amount": 700000, "description": "اصلاح مبلغ"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["data"]["credit"], 700000)

        resp = self.client.delete(f"/api/accounting/{entry_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AccountingEntry.objects.filter(pk=entry_id).exists())

    def test_system_entry_protected(self):
        sale = Sale.objects.create(
            customer=self.customer, amount=1000, discount=0, final_amount=1000
        )
        entry = AccountingEntry.objects.create(
            entry_type="sale", credit=1000, amount=1000, sale=sale, description="درآمد فروش"
        )
        # ویرایش جزئی (شرح/تاریخ) مجاز
        resp = self.client.put(
            f"/api/accounting/{entry.id}/",
            data=json.dumps({"description": "شرح اصلاح‌شده"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.description, "شرح اصلاح‌شده")
        # حذف ممنوع → حذف مجاز
        resp = self.client.delete(f"/api/accounting/{entry.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AccountingEntry.objects.filter(pk=entry.id).exists())
        # تغییر مبلغ روی سند سیستمی — در حالت partial نادیده گرفته می‌شود (مبلغ تغییر نمی‌کند)
        entry2 = AccountingEntry.objects.create(
            entry_type="sale", credit=1000, amount=1000, sale=sale, description="درآمد"
        )
        resp = self.client.put(
            f"/api/accounting/{entry2.id}/",
            data=json.dumps({"credit": 1, "amount": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        entry2.refresh_from_db()
        self.assertEqual(int(entry2.credit), 1000)

    def test_sale_delete_removes_accounting_entries(self):
        from logic.sales import record_sale

        make_user("sm", role=roles.SALES_MANAGER)
        sm = Client()
        sm.login(username="sm", password="secret123")
        sale = record_sale(self.customer, Decimal("5000000"), payment_status="unpaid")
        self.assertGreater(AccountingEntry.objects.filter(sale=sale).count(), 0)
        resp = sm.delete(f"/api/sales/{sale.id}/")
        self.assertEqual(resp.status_code, 200)
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertGreater(body["data"]["accounting_entries_deleted"], 0)
        self.assertEqual(AccountingEntry.objects.filter(sale=sale).count(), 0)

    def test_approved_entry_not_editable(self):
        entry_id = parse(self._create_manual_entry(is_approved=True))["data"]["id"]
        resp = self.client.put(
            f"/api/accounting/{entry_id}/",
            data=json.dumps({"credit": 1000}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_bulk_approve(self):
        self._create_manual_entry()
        self._create_manual_entry(description="سند دوم")
        resp = self.client.post(
            "/api/accounting/bulk-approve/", data="{}", content_type="application/json"
        )
        body = parse(resp)
        self.assertEqual(body["data"]["approved_count"], 2)
        self.assertEqual(AccountingEntry.objects.filter(is_approved=False).count(), 0)

    def test_list_filters_and_pagination(self):
        self._create_manual_entry(entry_type="adjustment", description="اصلاحیه")
        self._create_manual_entry(entry_type="other", description="متفرقه")
        resp = self.client.get("/api/accounting/?type=adjustment")
        body = parse(resp)
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(body["data"]["results"][0]["entry_type"], "adjustment")

        resp = self.client.get("/api/accounting/?search=متفرقه")
        self.assertEqual(parse(resp)["data"]["total"], 1)

        resp = self.client.get("/api/accounting/?limit=1&offset=0")
        body = parse(resp)
        self.assertEqual(body["data"]["total"], 2)
        self.assertEqual(len(body["data"]["results"]), 1)

    def test_operator_cannot_access_accounting(self):
        op_client = Client()
        op_client.login(username="op", password="secret123")
        resp = op_client.get("/api/accounting/")
        self.assertEqual(resp.status_code, 403)
        resp = op_client.post(
            "/api/accounting/bulk-approve/", data="{}", content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_summary_totals(self):
        Sale.objects.create(
            customer=self.customer,
            amount=2000,
            discount=0,
            final_amount=2000,
            paid_amount=500,
            payment_status="installment",
        )
        self._create_manual_entry(credit=100000)
        resp = self.client.get("/api/accounting/summary/")
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["total_balance_due"], 1500)
        self.assertEqual(body["data"]["open_invoices_count"], 1)
        self.assertEqual(body["data"]["pending_count"], 1)


class UserManagementTest(TestCase):
    def setUp(self):
        make_user("adm", role=roles.ADMIN)
        self.client = Client()
        self.client.login(username="adm", password="secret123")

    def test_update_user_role_and_branch(self):
        from backend.models import StaffProfile

        target = make_user("seller1", role=roles.OPERATOR)
        StaffProfile.objects.filter(user=target).update(branch="branch_1")
        resp = self.client.put(
            f"/api/auth/users/{target.id}/",
            data=json.dumps({"role": roles.SALES_MANAGER, "branch": "branch_2"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["role"], roles.SALES_MANAGER)
        self.assertEqual(body["data"]["branch"], "branch_2")

    def test_pending_clears_staff_profile(self):
        from auth.views import ensure_staff_profile
        from backend.models import StaffProfile

        target = make_user("acc1", role=roles.ACCOUNTANT)
        ensure_staff_profile(target, "branch_1")
        self.assertTrue(StaffProfile.objects.filter(user=target).exists())
        resp = self.client.put(
            f"/api/auth/users/{target.id}/",
            data=json.dumps({"role": roles.PENDING}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(StaffProfile.objects.filter(user=target).exists())

    def test_roles_include_descriptions(self):
        resp = self.client.get("/api/auth/roles/")
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertTrue(any("description" in r for r in body["data"]["results"]))
