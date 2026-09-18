"""تست برنامه‌های کش‌بک RFM: کسب، سقف مصرف، پله اپسل، سه حالت و برگشت."""

import json

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from backend.models import (
    CashbackProgram,
    Customer,
    CustomerRfmScore,
    RfmSegment,
)
from logic.cashback import create_program, matching_program, quote_cashback, usable_percent
from logic.rfm import seed_rfm_defaults
from logic.role_definitions import seed_builtin_roles
from logic.sales import delete_sale, record_sale
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def make_customer(name="علی", phone="09120000001"):
    return Customer.objects.create(full_name=name, phone=phone)


def make_program(**kwargs):
    steps = kwargs.pop("steps", [])
    segments = kwargs.pop("segments", [])
    data = {
        "name": kwargs.pop("name", "کش‌بک عمومی"),
        "earn_percent": kwargs.pop("earn_percent", 10),
        "base_usable_percent": kwargs.pop("base_usable_percent", 30),
        "redeem_mode": kwargs.pop("redeem_mode", CashbackProgram.REDEEM_MANUAL),
        "sort_order": kwargs.pop("sort_order", 0),
        "is_active": kwargs.pop("is_active", True),
        "segment_ids": [item.id for item in segments],
        "unlock_steps": steps,
    }
    data.update(kwargs)
    return create_program(data)


class CashbackEngineTests(TestCase):
    def setUp(self):
        seed_rfm_defaults()
        self.customer = make_customer()

    def test_earn_after_paid_sale(self):
        make_program(earn_percent=10, base_usable_percent=100, redeem_mode=CashbackProgram.REDEEM_MANUAL)
        record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.cashback_balance), 100000)

    def test_base_usable_cap(self):
        make_program(earn_percent=10, base_usable_percent=30)
        record_sale(self.customer, Decimal("1000000"))
        quote = quote_cashback(self.customer, Decimal("2000000"))
        self.assertEqual(quote["balance"], 100000)
        self.assertEqual(quote["usable_percent"], 30)
        self.assertEqual(quote["usable_amount"], 30000)

    def test_unlock_step_on_larger_invoice(self):
        make_program(
            earn_percent=10,
            base_usable_percent=30,
            steps=[{"extra_purchase_percent": 10, "extra_usable_percent": 20}],
        )
        record_sale(self.customer, Decimal("1000000"))
        quote = quote_cashback(self.customer, Decimal("1100000"))
        self.assertEqual(quote["usable_percent"], 50)
        self.assertEqual(quote["usable_amount"], 50000)
        low = quote_cashback(self.customer, Decimal("1000000"))
        self.assertEqual(low["usable_percent"], 30)

    def test_auto_each_sale_spends_usable_cap(self):
        make_program(
            earn_percent=10,
            base_usable_percent=100,
            redeem_mode=CashbackProgram.REDEEM_AUTO,
        )
        record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.cashback_balance), 100000)
        sale = record_sale(self.customer, Decimal("500000"))
        self.assertEqual(sale.discount_type, "cashback")
        self.assertEqual(sale.discount, Decimal("100000"))
        self.assertEqual(sale.final_amount, Decimal("400000"))
        self.assertEqual(int(self.customer.cashback_balance), 40000)

    def test_wallet_credit_mode(self):
        make_program(
            earn_percent=10,
            base_usable_percent=30,
            redeem_mode=CashbackProgram.REDEEM_WALLET,
        )
        record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.wallet_balance), 30000)
        self.assertEqual(int(self.customer.cashback_balance), 70000)

    def test_manual_does_not_auto_spend(self):
        make_program(earn_percent=10, base_usable_percent=100, redeem_mode=CashbackProgram.REDEEM_MANUAL)
        sale = record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(sale.discount_type, "amount")
        self.assertEqual(sale.discount, Decimal("0"))
        self.assertEqual(int(self.customer.cashback_balance), 100000)

    def test_no_earn_on_cashback_portion(self):
        make_program(earn_percent=10, base_usable_percent=100, redeem_mode=CashbackProgram.REDEEM_MANUAL)
        record_sale(self.customer, Decimal("1000000"))
        sale = record_sale(
            self.customer,
            Decimal("1000000"),
            discount_type="cashback",
            discount_value=Decimal("100000"),
        )
        self.assertEqual(sale.discount, Decimal("100000"))
        self.assertEqual(sale.paid_amount, Decimal("900000"))
        self.assertEqual(int(self.customer.cashback_balance), 90000)

    def test_delete_sale_reverses_cashback(self):
        make_program(earn_percent=10, base_usable_percent=30, redeem_mode=CashbackProgram.REDEEM_WALLET)
        sale = record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.wallet_balance), 30000)
        delete_sale(sale)
        self.assertEqual(int(self.customer.cashback_balance), 0)
        self.assertEqual(int(self.customer.wallet_balance), 0)

    def test_program_priority_first_sort_order_wins(self):
        champ = RfmSegment.objects.get(slug="champions")
        make_program(name="کم", earn_percent=10, sort_order=0, segments=[champ])
        make_program(name="زیاد", earn_percent=50, sort_order=1, segments=[champ])
        CustomerRfmScore.objects.create(
            customer=self.customer,
            rfm_code="555",
            r_score=5,
            f_score=5,
            m_score=5,
            segment=champ,
        )
        chosen = matching_program(self.customer)
        self.assertEqual(chosen.name, "کم")
        record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.cashback_balance), 100000)

    def test_segment_mismatch_skips_program(self):
        champ = RfmSegment.objects.get(slug="champions")
        make_program(name="فقط قهرمان", earn_percent=10, segments=[champ])
        record_sale(self.customer, Decimal("1000000"))
        self.assertEqual(int(self.customer.cashback_balance), 0)

    def test_usable_percent_highest_matching_step(self):
        program = make_program(
            base_usable_percent=20,
            steps=[
                {"extra_purchase_percent": 10, "extra_usable_percent": 10},
                {"extra_purchase_percent": 25, "extra_usable_percent": 40},
            ],
        )
        self.assertEqual(usable_percent(program, 1250000, 1000000), Decimal("60"))
        self.assertEqual(usable_percent(program, 1100000, 1000000), Decimal("30"))
        self.assertEqual(usable_percent(program, 1000000, 1000000), Decimal("20"))


class CashbackApiTests(TestCase):
    def setUp(self):
        seed_builtin_roles()
        ensure_legacy_test_roles()
        seed_rfm_defaults()
        self.admin = User.objects.create_user(username="cb-admin", password="secret123")
        roles.assign_role(self.admin, roles.ADMIN)
        self.client = Client()
        self.client.login(username="cb-admin", password="secret123")
        self.customer = make_customer()

    def test_create_program_and_quote(self):
        resp = self.client.post(
            "/api/rfm/cashback/programs/",
            data=json.dumps({
                "name": "باشگاه",
                "earn_percent": 10,
                "base_usable_percent": 30,
                "redeem_mode": "manual",
                "unlock_steps": [
                    {"extra_purchase_percent": 10, "extra_usable_percent": 20},
                    {"extra_purchase_percent": 25, "extra_usable_percent": 40},
                ],
            }),
            content_type="application/json",
        )
        body = json.loads(resp.content)
        self.assertTrue(body["ok"], body)
        program_id = body["data"]["id"]
        record_sale(self.customer, Decimal("1000000"))
        resp = self.client.get(
            f"/api/rfm/cashback/quote/?customer_id={self.customer.id}&amount=1100000"
        )
        quote = json.loads(resp.content)["data"]
        self.assertEqual(quote["program_id"], program_id)
        self.assertEqual(quote["usable_percent"], 50)
        self.assertEqual(quote["usable_amount"], 50000)
        self.assertGreater(quote["next_unlock"]["extra_amount"], 0)

    def test_operator_cannot_manage_programs(self):
        op = User.objects.create_user(username="cb-op", password="secret123")
        roles.assign_role(op, roles.OPERATOR)
        client = Client()
        client.login(username="cb-op", password="secret123")
        resp = client.post(
            "/api/rfm/cashback/programs/",
            data=json.dumps({"name": "ممنوع", "earn_percent": 5}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
