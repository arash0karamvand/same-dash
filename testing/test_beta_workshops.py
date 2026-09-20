"""تست واحدهای کارگاهی بتا: نجاری، رنگ، رویه‌کوبی، پارچه و کنترل کیفیت."""

import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from auth.permissions import (
    MANAGE_BETA_CARPENTRY,
    MANAGE_BETA_FABRIC,
    MANAGE_BETA_PAINT,
    MANAGE_BETA_QC,
    MANAGE_BETA_UPHOLSTERY,
    VIEW_BETA_CARPENTRY,
    VIEW_BETA_FABRIC,
    VIEW_BETA_PAINT,
    VIEW_BETA_QC,
    VIEW_BETA_UPHOLSTERY,
)
from backend.models import (
    BetaCarpentryOrder,
    BetaCarpentryWorkshop,
    BetaFabricDispatch,
    BetaFabricRoll,
    BetaPaintOrder,
    BetaQcInspection,
    BetaUpholsteryJob,
    Customer,
    Frame,
    Sale,
    SaleLineItem,
)
from logic import beta_workshops as L
from testing.role_helpers import ensure_test_role

User = get_user_model()
PASSWORD = "testpass123"

BETA_MANAGE_PERMS = [
    VIEW_BETA_CARPENTRY,
    MANAGE_BETA_CARPENTRY,
    VIEW_BETA_PAINT,
    MANAGE_BETA_PAINT,
    VIEW_BETA_UPHOLSTERY,
    MANAGE_BETA_UPHOLSTERY,
    VIEW_BETA_FABRIC,
    MANAGE_BETA_FABRIC,
    VIEW_BETA_QC,
    MANAGE_BETA_QC,
]


def _json(response):
    return json.loads(response.content)


class BetaHelperTests(TestCase):
    def test_clamp_progress_bounds(self):
        self.assertEqual(L._clamp_progress(None), 0)
        self.assertEqual(L._clamp_progress(-10), 0)
        self.assertEqual(L._clamp_progress(40), 40)
        self.assertEqual(L._clamp_progress(150), 100)

    def test_money_and_qty_parse_and_reject_invalid(self):
        self.assertEqual(L._money("1,250"), Decimal("1250"))
        self.assertEqual(L._qty(""), Decimal("0"))
        with self.assertRaisesMessage(ValueError, "مبلغ نمی‌تواند منفی باشد"):
            L._money(-1)
        with self.assertRaisesMessage(ValueError, "مقدار نامعتبر است"):
            L._qty("abc")
        with self.assertRaisesMessage(ValueError, "مقدار نمی‌تواند منفی باشد"):
            L._qty("-2")

    def test_date_and_choice_validation(self):
        self.assertEqual(L._date("2026-09-20"), date(2026, 9, 20))
        self.assertEqual(L._date(date(2026, 1, 2)), date(2026, 1, 2))
        self.assertIsNone(L._date(""))
        with self.assertRaisesMessage(ValueError, "تاریخ نامعتبر است"):
            L._date("20-09-2026")
        self.assertEqual(L._choice("", {"a"}, "نوع", default="a"), "a")
        with self.assertRaisesMessage(ValueError, "نوع را انتخاب کنید"):
            L._choice("", {"a"}, "نوع")
        with self.assertRaisesMessage(ValueError, "نوع نامعتبر است"):
            L._choice("z", {"a"}, "نوع")

    def test_notes_log_accepts_list_or_text(self):
        self.assertEqual(L._notes_log(["یک", "  ", "دو"]), ["یک", "دو"])
        self.assertEqual(L._notes_log("یادداشت"), ["یادداشت"])
        self.assertEqual(L._notes_log(""), [])


class BetaCarpentryLogicTests(TestCase):
    def test_no_workshop_is_created_without_user_input(self):
        self.assertEqual(L.list_workshops(), [])
        self.assertEqual(BetaCarpentryWorkshop.objects.count(), 0)

    def test_workshop_crud_and_blocked_delete(self):
        workshop = L.create_workshop({"name": "نجاری تست", "kind": "satellite"})
        self.assertEqual(workshop.kind, BetaCarpentryWorkshop.KIND_SATELLITE)
        L.update_workshop(workshop, {"name": "نجاری ویرایش", "is_active": False})
        workshop.refresh_from_db()
        self.assertEqual(workshop.name, "نجاری ویرایش")
        self.assertFalse(workshop.is_active)

        active = L.create_workshop({"name": "واحد فعال"})
        L.create_carpentry_order({"workshop_id": active.id, "product_name": "کلاف لونا"})
        with self.assertRaisesMessage(ValueError, "قابل حذف نیست"):
            L.delete_workshop(active)
        L.delete_workshop(workshop)
        self.assertFalse(BetaCarpentryWorkshop.objects.filter(pk=workshop.pk).exists())

    def test_create_order_requires_workshop_and_product(self):
        with self.assertRaisesMessage(ValueError, "واحد نجاری را انتخاب کنید"):
            L.create_carpentry_order({"product_name": "کلاف"})
        workshop = L.create_workshop({"name": "نجاری مرکزی"})
        with self.assertRaisesMessage(ValueError, "نام محصول"):
            L.create_carpentry_order({"workshop_id": workshop.id, "product_name": "  "})

    def test_order_create_filter_stats_and_missing_sale(self):
        workshop = L.create_workshop({"name": "نجاری مرکزی"})
        order = L.create_carpentry_order({
            "workshop_id": workshop.id,
            "product_name": "کلاف لونا",
            "kind": "repair",
            "customer_name": "علی",
            "order_ref": "SO-11",
            "quantity": 2,
            "freight_cost": "15,000",
            "note": "شروع ساخت",
        })
        self.assertTrue(order.code.startswith("CRF-"))
        self.assertEqual(order.kind, BetaCarpentryOrder.KIND_REPAIR)
        self.assertEqual(order.freight_cost, Decimal("15000"))
        self.assertEqual(order.notes_log, ["شروع ساخت"])

        L.update_carpentry_order(order, {"status": BetaCarpentryOrder.STATUS_READY})
        payload = L.carpentry_order_to_dict(order)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["workshop_name"], "نجاری مرکزی")

        filtered = list(L.filter_carpentry_orders(
            BetaCarpentryOrder.objects.all(),
            {"search": "لونا", "kind": "repair", "workshop_id": workshop.id},
        ))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(list(L.filter_carpentry_orders(BetaCarpentryOrder.objects.all(), {"search": "ناموجود"})), [])

        stats = L.carpentry_stats()
        self.assertEqual(stats["by_kind"]["repair"], 1)
        self.assertEqual(stats["by_status"]["ready"], 1)
        self.assertEqual(stats["freight_cost"], 15000)
        self.assertEqual([opt["value"] for opt in stats["statuses"]], ["in_progress", "ready", "delivered"])

        with self.assertRaisesMessage(ValueError, "سفارش یافت نشد"):
            L.create_carpentry_order({
                "workshop_id": workshop.id,
                "product_name": "کلاف",
                "sale_id": 999999,
            })

    def test_create_order_from_linked_sale_and_frame(self):
        customer = Customer.objects.create(full_name="علی رضایی", phone="09120000000")
        frame = Frame.objects.create(name="کلاف لونا", wood_type=Frame.WOOD_WALNUT)
        sale = Sale.objects.create(
            customer=customer,
            invoice_number="INV-100",
            workflow_stage_id=Sale.WORKFLOW_STAGE_IN_PRODUCTION,
            fulfillment_route=Sale.FULFILLMENT_ROUTE_FACTORY,
            amount=10_000_000,
            final_amount=10_000_000,
        )
        SaleLineItem.objects.create(
            sale=sale,
            frame=frame,
            product_name="مبل لونا",
            quantity=2,
            unit_price=5_000_000,
            line_total=10_000_000,
        )
        workshop = L.create_workshop({"name": "نجاری مرکزی"})
        order = L.create_carpentry_order({
            "workshop_id": workshop.id,
            "sale_id": sale.id,
        })
        self.assertEqual(order.sale_id, sale.id)
        self.assertEqual(order.frame_id, frame.id)
        self.assertEqual(order.customer_name, "علی رضایی")
        self.assertEqual(order.order_ref, "INV-100")
        self.assertEqual(order.product_name, "کلاف لونا")
        self.assertEqual(order.quantity, 2)
        self.assertIn("گردو", order.wood_type)

        sources = L.carpentry_sources()
        self.assertTrue(any(row["id"] == sale.id for row in sources["sales"]))
        self.assertTrue(any(row["id"] == frame.id for row in sources["frames"]))


class BetaPaintLogicTests(TestCase):
    def test_create_advance_and_final_stage(self):
        order = L.create_paint_order({
            "product_name": "مبل چستر",
            "kind": "qc_return",
            "color_name": "گردویی",
            "note": "ورود خط",
        })
        self.assertEqual(order.stage, BetaPaintOrder.STAGE_RAW)
        self.assertEqual(order.kind, BetaPaintOrder.KIND_QC_RETURN)
        self.assertEqual(order.notes_log, ["ورود خط"])

        advanced = L.advance_paint_order(order, "سنباده شد")
        self.assertEqual(advanced.stage, BetaPaintOrder.STAGE_SANDING)
        self.assertEqual(advanced.progress, 14)
        self.assertIn("سنباده شد", advanced.notes_log)

        order.stage = BetaPaintOrder.STAGE_QC
        order.save(update_fields=["stage"])
        with self.assertRaisesMessage(ValueError, "آخرین مرحله"):
            L.advance_paint_order(order)

        stats = L.paint_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["by_kind"]["qc_return"], 1)
        self.assertEqual(stats["delivered"], 1)
        self.assertEqual(stats["final_stage"], BetaPaintOrder.STAGE_QC)

    def test_filter_paint_orders(self):
        first = L.create_paint_order({"product_name": "کلاف خام", "color_name": "سفید"})
        L.create_paint_order({"product_name": "تعمیر دسته", "kind": "repair"})
        L.advance_paint_order(first)
        found = list(L.filter_paint_orders(BetaPaintOrder.objects.all(), {"kind": "normal", "stage": "sanding"}))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].product_name, "کلاف خام")


class BetaUpholsteryLogicTests(TestCase):
    def test_create_advance_and_done_flag(self):
        job = L.create_upholstery_job({
            "product_name": "مبل راحتی",
            "craftsman": "استاد رضا",
            "foam_material": "فوم سرد",
        })
        self.assertEqual(job.stage, BetaUpholsteryJob.STAGE_WEBBING)
        self.assertFalse(L.upholstery_job_to_dict(job)["is_done"])

        L.advance_upholstery_job(job)
        self.assertEqual(job.stage, BetaUpholsteryJob.STAGE_FOAM)
        self.assertEqual(job.progress, 25)

        job.stage = BetaUpholsteryJob.STAGE_QC
        job.progress = 80
        job.save(update_fields=["stage", "progress"])
        L.advance_upholstery_job(job)
        job.refresh_from_db()
        self.assertEqual(job.stage, BetaUpholsteryJob.STAGE_QC)
        self.assertEqual(job.progress, 100)
        self.assertTrue(L.upholstery_job_to_dict(job)["is_done"])

        stats = L.upholstery_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["ready_for_qc"], 1)
        self.assertEqual(stats["assembling"], 0)

    def test_upholstery_stats_respects_search(self):
        L.create_upholstery_job({"product_name": "مبل آلفا", "order_ref": "A-1"})
        L.create_upholstery_job({"product_name": "مبل بتا", "order_ref": "B-1"})
        all_stats = L.upholstery_stats()
        filtered = L.upholstery_stats({"search": "آلفا"})
        self.assertEqual(all_stats["total"], 2)
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["by_stage"][BetaUpholsteryJob.STAGE_WEBBING], 1)


class BetaFabricLogicTests(TestCase):
    def test_roll_value_dispatch_and_overdraw(self):
        roll = L.create_fabric_roll({
            "color_name": "کرم",
            "company": "هارمونی",
            "fabric_type": "مخمل",
            "unit_cost": 100000,
            "meters": 20,
            "min_meters": 18,
        })
        self.assertTrue(roll.code.startswith("FB-"))
        payload = L.fabric_roll_to_dict(roll)
        self.assertEqual(payload["value"], 2_000_000)
        self.assertFalse(payload["low_stock"])

        dispatch = L.create_fabric_dispatch({
            "roll_id": roll.id,
            "destination": "رویه‌کوبی",
            "meters": 5,
            "sent_date": "2026-09-20",
        })
        roll.refresh_from_db()
        self.assertEqual(Decimal(roll.meters), Decimal("15"))
        self.assertEqual(dispatch.destination, "رویه‌کوبی")
        self.assertTrue(L.fabric_roll_to_dict(roll)["low_stock"])

        with self.assertRaisesMessage(ValueError, "از موجودی طاقه بیشتر است"):
            L.create_fabric_dispatch({"roll_id": roll.id, "destination": "رنگ", "meters": 40})
        with self.assertRaisesMessage(ValueError, "بیشتر از صفر"):
            L.create_fabric_dispatch({"roll_id": roll.id, "destination": "رنگ", "meters": 0})

        stats = L.fabric_stats()
        self.assertEqual(stats["rolls"], 1)
        self.assertEqual(stats["dispatches"], 1)
        self.assertEqual(stats["low_stock"], 1)
        self.assertEqual(stats["meters"], 15.0)


class BetaQcLogicTests(TestCase):
    def test_create_evaluate_and_archive_filter(self):
        item = L.create_qc_inspection({
            "product_name": "مبل چستر",
            "buyer_name": "خریدار",
            "order_ref": "SO-90",
            "quantity": 2,
        })
        self.assertEqual(item.status, BetaQcInspection.STATUS_PENDING)
        self.assertTrue(item.code.startswith("QC-"))

        L.evaluate_qc_inspection(item, {"status": "rework", "grade": "B"})
        item.refresh_from_db()
        self.assertEqual(item.status, BetaQcInspection.STATUS_REWORK)
        self.assertEqual(item.grade, "B")

        approved = L.create_qc_inspection({"product_name": "صندلی"})
        L.evaluate_qc_inspection(approved, {"status": "approved", "grade": "A"})

        archive = list(L.filter_qc_inspections(BetaQcInspection.objects.all(), {"archive": "1"}))
        current = list(L.filter_qc_inspections(BetaQcInspection.objects.all(), {"archive": "0"}))
        self.assertEqual([row.status for row in archive], [BetaQcInspection.STATUS_APPROVED])
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].status, BetaQcInspection.STATUS_REWORK)

        with self.assertRaisesMessage(ValueError, "گرید نامعتبر است"):
            L.evaluate_qc_inspection(item, {"status": "approved", "grade": "Z"})

        stats = L.qc_stats()
        self.assertEqual(stats["by_status"]["pending"], 0)
        self.assertEqual(stats["by_status"]["rework"], 1)
        self.assertEqual(stats["approved"], 1)
        self.assertEqual(stats["current"], 1)
        self.assertEqual(stats["archive_status"], BetaQcInspection.STATUS_APPROVED)

    def test_qc_stats_respects_search(self):
        L.create_qc_inspection({"product_name": "مبل آلفا", "order_ref": "A-1"})
        L.create_qc_inspection({"product_name": "صندلی بتا", "order_ref": "B-1"})
        all_stats = L.qc_stats()
        filtered = L.qc_stats({"search": "آلفا"})
        self.assertEqual(all_stats["total"], 2)
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["current"], 1)


class BetaWorkshopApiTests(TestCase):
    def setUp(self):
        ensure_test_role("beta_manager", BETA_MANAGE_PERMS, label="مدیر واحدهای بتا")
        ensure_test_role("beta_viewer", [VIEW_BETA_CARPENTRY], label="مشاهده نجاری بتا")
        self.manager = User.objects.create_user(username="beta_mgr", password=PASSWORD)
        roles.assign_role(self.manager, "beta_manager")
        self.viewer = User.objects.create_user(username="beta_view", password=PASSWORD)
        roles.assign_role(self.viewer, "beta_viewer")
        self.client = Client()

    def _login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def test_unauthenticated_and_forbidden(self):
        resp = self.client.get("/api/beta/carpentry/stats/")
        self.assertEqual(resp.status_code, 401)
        self._login(self.viewer)
        denied = self.client.post(
            "/api/beta/carpentry/workshops/",
            data=json.dumps({"name": "واحد ممنوع"}),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        paint = self.client.get("/api/beta/paint/stats/")
        self.assertEqual(paint.status_code, 403)

    def test_carpentry_workshop_and_order_api(self):
        self._login(self.manager)
        stats = self.client.get("/api/beta/carpentry/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(_json(stats)["data"]["workshops"], 0)

        created = self.client.post(
            "/api/beta/carpentry/workshops/",
            data=json.dumps({"name": "نجاری API", "kind": "internal"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        workshop_id = _json(created)["data"]["id"]

        order = self.client.post(
            "/api/beta/carpentry/orders/",
            data=json.dumps({
                "workshop_id": workshop_id,
                "product_name": "کلاف API",
                "quantity": 3,
                "freight_cost": 8000,
            }),
            content_type="application/json",
        )
        self.assertEqual(order.status_code, 201, order.content)
        self.assertEqual(_json(order)["data"]["product_name"], "کلاف API")
        self.assertEqual(_json(order)["data"]["freight_cost"], 8000)

    def test_paint_advance_api(self):
        self._login(self.manager)
        created = self.client.post(
            "/api/beta/paint/orders/",
            data=json.dumps({"product_name": "مبل رنگ", "color_name": "گردویی"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        pk = _json(created)["data"]["id"]
        advanced = self.client.post(
            f"/api/beta/paint/orders/{pk}/advance/",
            data=json.dumps({"note": "مرحله بعد"}),
            content_type="application/json",
        )
        self.assertEqual(advanced.status_code, 200, advanced.content)
        self.assertEqual(_json(advanced)["data"]["stage"], BetaPaintOrder.STAGE_SANDING)

    def test_upholstery_and_qc_api(self):
        self._login(self.manager)
        job = self.client.post(
            "/api/beta/upholstery/jobs/",
            data=json.dumps({"product_name": "مبل راحتی", "craftsman": "رضا"}),
            content_type="application/json",
        )
        self.assertEqual(job.status_code, 201, job.content)
        job_id = _json(job)["data"]["id"]
        advanced = self.client.post(f"/api/beta/upholstery/jobs/{job_id}/advance/", data="{}", content_type="application/json")
        self.assertEqual(advanced.status_code, 200)
        self.assertEqual(_json(advanced)["data"]["stage"], BetaUpholsteryJob.STAGE_FOAM)

        qc = self.client.post(
            "/api/beta/qc/inspections/",
            data=json.dumps({"product_name": "مبل QC", "buyer_name": "خریدار"}),
            content_type="application/json",
        )
        self.assertEqual(qc.status_code, 201, qc.content)
        qc_id = _json(qc)["data"]["id"]
        evaluated = self.client.post(
            f"/api/beta/qc/inspections/{qc_id}/evaluate/",
            data=json.dumps({"status": "approved", "grade": "A"}),
            content_type="application/json",
        )
        self.assertEqual(evaluated.status_code, 200, evaluated.content)
        self.assertEqual(_json(evaluated)["data"]["status"], "approved")
        self.assertEqual(_json(evaluated)["data"]["grade"], "A")

    def test_fabric_dispatch_reduces_stock_via_api(self):
        self._login(self.manager)
        roll = self.client.post(
            "/api/beta/fabric/rolls/",
            data=json.dumps({
                "color_name": "آبی",
                "company": "هارمونی",
                "meters": 12,
                "unit_cost": 50000,
                "min_meters": 2,
            }),
            content_type="application/json",
        )
        self.assertEqual(roll.status_code, 201, roll.content)
        roll_id = _json(roll)["data"]["id"]
        dispatch = self.client.post(
            "/api/beta/fabric/dispatches/",
            data=json.dumps({"roll_id": roll_id, "destination": "رویه‌کوبی", "meters": 4}),
            content_type="application/json",
        )
        self.assertEqual(dispatch.status_code, 201, dispatch.content)
        detail = self.client.get(f"/api/beta/fabric/rolls/{roll_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(_json(detail)["data"]["meters"], 8.0)

        self.assertTrue(BetaFabricDispatch.objects.filter(roll_id=roll_id).exists())
