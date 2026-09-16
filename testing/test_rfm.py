"""تست موتور RFM، بخش‌بندی، کش امتیاز، پیامک و دسترسی API."""

import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from auth import roles
from backend.models import (
    Customer,
    CustomerRfmScore,
    RfmActionLog,
    RfmSegment,
    RfmSettings,
    Sale,
    SMSLog,
)
from logic.rfm import (
    assign_quantile_scores,
    create_segment,
    extract_raw_metrics,
    match_segment,
    recalculate_all_rfm,
    score_by_min_thresholds,
    score_by_r_thresholds,
    seed_rfm_defaults,
    send_segment_sms,
    update_settings,
)
from logic.role_definitions import seed_builtin_roles
from testing.role_helpers import ensure_legacy_test_roles

User = get_user_model()


def parse(response):
    return json.loads(response.content)


def make_user(username, role=roles.OPERATOR, password="secret123"):
    ensure_legacy_test_roles()
    user = User.objects.create_user(username=username, password=password)
    roles.assign_role(user, role)
    return user


def make_customer(name, phone):
    return Customer.objects.create(full_name=name, phone=phone)


def make_sale(customer, amount, days_ago, *, cancelled=False, paid=None):
    sold_at = timezone.now() - timedelta(days=days_ago)
    return Sale.objects.create(
        customer=customer,
        amount=amount,
        final_amount=amount,
        paid_amount=paid if paid is not None else amount,
        sold_at=sold_at,
        order_status="cancelled" if cancelled else "confirmed",
    )


class RfmScoringTest(TestCase):
    def test_quantile_inverts_recency(self):
        scores = assign_quantile_scores([1, 10, 30, 100, 400], invert=True, bins=5)
        self.assertEqual(scores, [5, 4, 3, 2, 1])

    def test_quantile_higher_frequency_wins(self):
        scores = assign_quantile_scores([1, 2, 3, 4, 5], invert=False, bins=5)
        self.assertEqual(scores, [1, 2, 3, 4, 5])

    def test_tied_values_share_score(self):
        scores = assign_quantile_scores([10, 10, 10], invert=True, bins=5)
        self.assertEqual(scores, [5, 5, 5])

    def test_threshold_recency(self):
        thresholds = [
            {"max_days": 90, "score": 5},
            {"max_days": 180, "score": 4},
            {"max_days": 365, "score": 3},
            {"max_days": 730, "score": 2},
            {"max_days": 99999, "score": 1},
        ]
        self.assertEqual(score_by_r_thresholds(50, thresholds), 5)
        self.assertEqual(score_by_r_thresholds(200, thresholds), 3)
        self.assertEqual(score_by_r_thresholds(800, thresholds), 1)

    def test_threshold_frequency_and_monetary(self):
        f_rows = [
            {"min_count": 5, "score": 5},
            {"min_count": 2, "score": 3},
            {"min_count": 1, "score": 1},
        ]
        m_rows = [
            {"min_amount": 100_000_000, "score": 5},
            {"min_amount": 10_000_000, "score": 3},
            {"min_amount": 0, "score": 1},
        ]
        self.assertEqual(score_by_min_thresholds(5, f_rows, "min_count"), 5)
        self.assertEqual(score_by_min_thresholds(2, f_rows, "min_count"), 3)
        self.assertEqual(score_by_min_thresholds(0, f_rows, "min_count"), 1)
        self.assertEqual(score_by_min_thresholds(150_000_000, m_rows, "min_amount"), 5)
        self.assertEqual(score_by_min_thresholds(11_000_000, m_rows, "min_amount"), 3)

    def test_empty_quantile_list(self):
        self.assertEqual(assign_quantile_scores([], invert=True), [])


class RfmEngineTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
        seed_rfm_defaults()
        self.champ = make_customer("قهرمان", "09120000001")
        self.sleeping = make_customer("خواب‌آلود", "09120000002")
        self.newbie = make_customer("تازه‌وارد", "09120000003")
        for days in (5, 20, 40, 60):
            make_sale(self.champ, 200_000_000, days)
        for days in (400, 430, 460, 500):
            make_sale(self.sleeping, 200_000_000, days)
        make_sale(self.newbie, 5_000_000, 3)

    def test_extracts_raw_metrics_and_skips_cancelled(self):
        ignored = make_customer("لغو", "09120000009")
        make_sale(ignored, 99_000_000, 1, cancelled=True)
        rows = {row["customer_id"]: row for row in extract_raw_metrics()}
        self.assertNotIn(ignored.id, rows)
        self.assertGreaterEqual(rows[self.champ.id]["f_raw"], 4)
        self.assertEqual(rows[self.newbie.id]["f_raw"], 1)
        self.assertLess(rows[self.champ.id]["r_raw"], rows[self.sleeping.id]["r_raw"])

    def test_recalculate_labels_furniture_segments(self):
        update_settings({"score_method": "threshold", "fm_window": "lookback", "lookback_days": 730})
        result = recalculate_all_rfm(send_actions=False)
        self.assertEqual(result["scored"], 3)
        by_customer = {
            item.customer_id: item
            for item in CustomerRfmScore.objects.select_related("segment")
        }
        self.assertEqual(by_customer[self.champ.id].segment.slug, "champions")
        self.assertEqual(by_customer[self.sleeping.id].segment.slug, "hibernating")
        self.assertEqual(by_customer[self.newbie.id].segment.slug, "newcomers")
        self.assertEqual(by_customer[self.champ.id].rfm_code[0], "5")

    def test_match_segment_priority(self):
        seed_rfm_defaults()
        segments = list(RfmSegment.objects.filter(is_active=True).order_by("sort_order", "id"))
        champ = match_segment(5, 5, 5, segments)
        self.assertEqual(champ.slug, "champions")
        self.assertIsNone(match_segment(3, 3, 3, segments))

    def test_skips_inactive_customer_and_pending_preinvoice(self):
        inactive = make_customer("غیرفعال", "09120000010")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        make_sale(inactive, 80_000_000, 2)
        pending = make_customer("پیش‌فاکتور", "09120000011")
        Sale.objects.create(
            customer=pending,
            amount=40_000_000,
            final_amount=40_000_000,
            paid_amount=0,
            sold_at=timezone.now() - timedelta(days=1),
            order_kind="pre_invoice",
            order_status="pending",
        )
        rows = {row["customer_id"]: row for row in extract_raw_metrics()}
        self.assertNotIn(inactive.id, rows)
        self.assertNotIn(pending.id, rows)

    def test_paid_amount_and_lifetime_window(self):
        customer = make_customer("نقدی", "09120000012")
        make_sale(customer, 80_000_000, 10, paid=20_000_000)
        make_sale(customer, 50_000_000, 800, paid=50_000_000)
        update_settings({"monetary_field": "paid_amount", "fm_window": "lookback", "lookback_days": 730})
        lookback = {row["customer_id"]: row for row in extract_raw_metrics()}
        self.assertEqual(int(lookback[customer.id]["m_raw"]), 20_000_000)
        self.assertEqual(lookback[customer.id]["f_raw"], 1)
        update_settings({"fm_window": "lifetime", "monetary_field": "paid_amount"})
        lifetime = {row["customer_id"]: row for row in extract_raw_metrics()}
        self.assertEqual(int(lifetime[customer.id]["m_raw"]), 70_000_000)
        self.assertEqual(lifetime[customer.id]["f_raw"], 2)

    def test_quantile_recalculate_writes_cache(self):
        update_settings({"score_method": "quantile"})
        result = recalculate_all_rfm(send_actions=False)
        self.assertEqual(result["scored"], 3)
        champ = CustomerRfmScore.objects.get(customer=self.champ)
        sleeping = CustomerRfmScore.objects.get(customer=self.sleeping)
        self.assertGreater(champ.r_score, sleeping.r_score)
        self.assertEqual(len(champ.rfm_code), 3)

    def test_recalculate_drops_stale_scores(self):
        update_settings({"score_method": "threshold"})
        recalculate_all_rfm(send_actions=False)
        gone = make_customer("حذف‌شونده", "09120000013")
        sale = make_sale(gone, 8_000_000, 1)
        recalculate_all_rfm(send_actions=False)
        self.assertTrue(CustomerRfmScore.objects.filter(customer=gone).exists())
        sale.order_status = "cancelled"
        sale.save()
        recalculate_all_rfm(send_actions=False)
        self.assertFalse(CustomerRfmScore.objects.filter(customer=gone).exists())

    def test_empty_score_lists_match_any(self):
        segment = create_segment(
            {
                "name": "همه اخیرها",
                "r_scores": [5],
                "f_scores": [],
                "m_scores": [],
                "action_type": "playbook",
                "sort_order": 99,
            }
        )
        self.assertTrue(match_segment(5, 1, 1, [segment]))
        self.assertIsNone(match_segment(1, 5, 5, [segment]))

    def test_seed_is_idempotent(self):
        seed_rfm_defaults()
        count = RfmSegment.objects.count()
        seed_rfm_defaults()
        self.assertEqual(RfmSegment.objects.count(), count)

    def test_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):
            update_settings({"score_method": "magic"})
        with self.assertRaises(ValueError):
            create_segment({"name": "   "})


class RfmSmsDedupTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
        seed_rfm_defaults()
        self.customer = make_customer("تازه‌وارد", "09121112233")
        make_sale(self.customer, 5_000_000, 2)
        segment = RfmSegment.objects.get(slug="newcomers")
        segment.auto_sms = True
        segment.save(update_fields=["auto_sms"])
        update_settings({"score_method": "threshold", "lookback_days": 730})

    def test_auto_sms_skips_within_cooldown(self):
        first = recalculate_all_rfm(send_actions=True)
        self.assertGreaterEqual(first["sms_sent"], 1)
        second = recalculate_all_rfm(send_actions=True)
        self.assertEqual(second["sms_sent"], 0)
        self.assertGreaterEqual(second["sms_skipped"], 1)
        self.assertEqual(SMSLog.objects.filter(sms_type="rfm").count(), 1)
        self.assertEqual(RfmActionLog.objects.count(), 1)

    def test_manual_send_force_bypasses_cooldown(self):
        recalculate_all_rfm(send_actions=True)
        score = CustomerRfmScore.objects.select_related("customer", "segment").get(
            customer_id=self.customer.id
        )
        result = send_segment_sms(score, ignore_cooldown=True)
        self.assertFalse(result["skipped"])
        self.assertEqual(SMSLog.objects.filter(sms_type="rfm").count(), 2)


class RfmApiTest(TestCase):
    def setUp(self):
        seed_builtin_roles()
        seed_rfm_defaults()

    def test_operator_cannot_view(self):
        make_user("op-rfm", role=roles.OPERATOR)
        client = Client()
        client.login(username="op-rfm", password="secret123")
        resp = client.get("/api/rfm/summary/")
        self.assertEqual(resp.status_code, 403)

    def test_office_role_can_view_and_admin_can_recalculate(self):
        make_user("office-rfm", role=roles.ACCOUNTING_FINANCE)
        office = Client()
        office.login(username="office-rfm", password="secret123")
        resp = office.get("/api/rfm/summary/")
        body = parse(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(body["ok"])
        slugs = {item["slug"] for item in body["data"]["segments"]}
        self.assertIn("champions", slugs)

        make_user("adm-rfm", role=roles.ADMIN)
        admin = Client()
        admin.login(username="adm-rfm", password="secret123")
        resp = admin.put(
            "/api/rfm/settings/",
            data=json.dumps({"score_method": "threshold", "lookback_days": 900}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(parse(resp)["data"]["lookback_days"], 900)

        resp = admin.post(
            "/api/rfm/recalculate/",
            data=json.dumps({"send_sms": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(parse(resp)["ok"])

    def test_operator_cannot_manage_segments(self):
        make_user("op-seg", role=roles.OPERATOR)
        client = Client()
        client.login(username="op-seg", password="secret123")
        resp = client.post(
            "/api/rfm/segments/",
            data=json.dumps({"name": "تست"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_gets_401(self):
        resp = Client().get("/api/rfm/summary/")
        self.assertEqual(resp.status_code, 401)

    def test_segment_crud_and_customer_filters(self):
        make_user("adm-crud", role=roles.ADMIN)
        client = Client()
        client.login(username="adm-crud", password="secret123")
        resp = client.post(
            "/api/rfm/segments/",
            data=json.dumps(
                {
                    "name": "نیاز به توجه",
                    "r_scores": [3],
                    "f_scores": [3],
                    "m_scores": [3],
                    "action_type": "call",
                    "action_title": "تماس پیگیری",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        pk = parse(resp)["data"]["id"]
        resp = client.put(
            f"/api/rfm/segments/{pk}/",
            data=json.dumps({"action_title": "تماس فوری", "auto_sms": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(parse(resp)["data"]["action_title"], "تماس فوری")

        customer = make_customer("فیلتر", "09123334455")
        make_sale(customer, 5_000_000, 2)
        client.post(
            "/api/rfm/recalculate/",
            data=json.dumps({"send_sms": False}),
            content_type="application/json",
        )
        score = CustomerRfmScore.objects.get(customer=customer)
        resp = client.get("/api/rfm/customers/?search=فیلتر")
        names = [row["full_name"] for row in parse(resp)["data"]["results"]]
        self.assertIn("فیلتر", names)
        if score.segment_id:
            resp = client.get(f"/api/rfm/customers/?segment_id={score.segment_id}")
            self.assertGreaterEqual(parse(resp)["data"]["total"], 1)
        resp = client.get("/api/rfm/customers/?segment_id=other")
        self.assertEqual(resp.status_code, 200)

        resp = client.delete(f"/api/rfm/segments/{pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(parse(resp)["data"]["deleted"])
        resp = client.put(
            "/api/rfm/segments/99999/",
            data=json.dumps({"name": "نیست"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_send_sms_api_requires_permission_and_score(self):
        make_user("office-sms", role=roles.ACCOUNTING_FINANCE)
        office = Client()
        office.login(username="office-sms", password="secret123")
        customer = make_customer("پیامکی", "09124445566")
        make_sale(customer, 5_000_000, 1)
        update_settings({"score_method": "threshold"})
        recalculate_all_rfm(send_actions=False)
        resp = office.post(
            f"/api/rfm/customers/{customer.id}/send-sms/",
            data=json.dumps({"force": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        make_user("adm-sms", role=roles.ADMIN)
        admin = Client()
        admin.login(username="adm-sms", password="secret123")
        resp = admin.post(
            f"/api/rfm/customers/{customer.id}/send-sms/",
            data=json.dumps({"force": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(parse(resp)["data"]["skipped"])
        resp = admin.post(
            "/api/rfm/customers/99999/send-sms/",
            data=json.dumps({"force": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_management_command_skip_sms(self):
        make_customer("کرون", "09125556677")
        make_sale(Customer.objects.get(phone="09125556677"), 9_000_000, 4)
        out = StringIO()
        call_command("recalculate_rfm", "--skip-sms", stdout=out)
        self.assertIn("RFM", out.getvalue())
        self.assertTrue(CustomerRfmScore.objects.exists())
        self.assertFalse(RfmActionLog.objects.exists())
        self.assertIsNotNone(RfmSettings.get_solo().last_run_at)
