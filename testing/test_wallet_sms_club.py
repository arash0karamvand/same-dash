"""تست کیف پول و پیامک باشگاه مشتریان."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import Customer, SMSLog, SmsClubSettings, WalletTransaction
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def make_user(username, password="secret123", role=roles.OPERATOR):
    ensure_legacy_test_roles()
    user = User.objects.create_user(username=username, password=password)
    roles.assign_role(user, role)
    return user


def parse(response):
    return json.loads(response.content)


class WalletApiTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone="09120000020")
        make_user("op", role=roles.OPERATOR)
        make_user("acc", role=roles.ACCOUNTANT)
        self.op = Client()
        self.op.login(username="op", password="secret123")
        self.acc = Client()
        self.acc.login(username="acc", password="secret123")

    def test_deposit_increases_balance(self):
        resp = self.op.post(
            f"/api/customers/{self.customer.id}/wallet/",
            data=json.dumps({"action": "deposit", "amount": 50000, "description": "هدیه"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(body["data"]["balance"], 50000)
        self.customer.refresh_from_db()
        self.assertEqual(int(self.customer.wallet_balance), 50000)
        self.assertEqual(WalletTransaction.objects.count(), 1)

    def test_withdraw_decreases_balance(self):
        from logic.wallet import adjust_wallet

        adjust_wallet(self.customer, 100000, description="opening balance")
        resp = self.acc.post(
            f"/api/customers/{self.customer.id}/wallet/",
            data=json.dumps({"action": "withdraw", "amount": 30000}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(body["data"]["balance"], 70000)

    def test_withdraw_insufficient_funds(self):
        resp = self.op.post(
            f"/api/customers/{self.customer.id}/wallet/",
            data=json.dumps({"action": "withdraw", "amount": 1000}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class SmsClubApiTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Sara", phone="09120000021")
        make_user("sm", role=roles.SALES_MANAGER)
        self.client = Client()
        self.client.login(username="sm", password="secret123")
        SmsClubSettings.get_solo()

    def test_club_settings_get_put(self):
        resp = self.client.get("/api/sms/club/settings/")
        self.assertTrue(parse(resp)["ok"])
        resp = self.client.put(
            "/api/sms/club/settings/",
            data=json.dumps({"auto_order_placed": False, "shop_name": "فروشگاه تست"}),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertTrue(body["ok"])
        self.assertFalse(body["data"]["auto_order_placed"])
        self.assertEqual(body["data"]["shop_name"], "فروشگاه تست")

    def test_send_discount_sms(self):
        resp = self.client.post(
            "/api/sms/club/send-discount/",
            data=json.dumps(
                {
                    "target": "single",
                    "customer_id": self.customer.id,
                    "discount_type": "percent",
                    "discount_value": 10,
                }
            ),
            content_type="application/json",
        )
        body = parse(resp)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(body["ok"])
        log = SMSLog.objects.filter(customer=self.customer, sms_type="discount").first()
        self.assertIsNotNone(log)
        self.assertIn("10", log.message)

    def test_order_placed_sms_on_sale(self):
        SmsClubSettings.objects.filter(pk=1).update(auto_order_placed=True)
        resp = self.client.post(
            "/api/sales/",
            data=json.dumps(
                {
                    "customer_id": self.customer.id,
                    "amount": 200000,
                    "payment_status": "paid",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        log = SMSLog.objects.filter(customer=self.customer, sms_type="order_placed").first()
        self.assertIsNotNone(log)

    def test_welcome_sms_on_customer_create(self):
        SmsClubSettings.objects.filter(pk=1).update(auto_welcome=True)
        resp = self.client.post(
            "/api/customers/",
            data=json.dumps({"full_name": "New User", "phone": "09120000022"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        log = SMSLog.objects.filter(sms_type="welcome", phone_number="09120000022").first()
        self.assertIsNotNone(log)
