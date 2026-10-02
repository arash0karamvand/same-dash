import json
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from backend.models import (
    Account,
    FinancialEvent,
    GoodsReceipt,
    InventoryCostLayer,
    InventoryTransaction,
    Material,
    MaterialSupplier,
    PurchaseOrder,
    PurchaseRequestLine,
)
from logic.accounting_accounts import get_account
from logic.document_attachments import create_attachment
from logic.ledger import LEGAL_LEDGER
from logic.procurement import (
    approve_goods_receipt,
    approve_request,
    generate_shortage_requests,
    receive_order,
)
from logic.stock_locations import ensure_central_warehouse
from testing.accounting_helpers import seed_accounts


class ProcurementPhaseThreeTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        seed_accounts(ledger=LEGAL_LEDGER)
        self.user = get_user_model().objects.create_superuser(
            username="procurement-admin",
            email="procurement@example.test",
            password="secret123",
        )
        self.plain = get_user_model().objects.create_user(
            username="procurement-plain", password="secret123"
        )
        self.material = Material.objects.create(name="Procurement material", unit_cost=0)
        self.warehouse = ensure_central_warehouse()
        self.location = {
            "kind": InventoryTransaction.LOCATION_WAREHOUSE,
            "warehouse": self.warehouse,
            "warehouse_id": self.warehouse.pk,
            "branch": None,
        }
        payable = get_account("accounts_payable", ledger=LEGAL_LEDGER)
        supplier_account = Account.objects.create(
            ledger=payable.ledger,
            parent=payable,
            slug="supplier-procurement-test",
            code="PT01",
            name="Procurement supplier",
            account_class=payable.account_class,
            normal_balance=payable.normal_balance,
        )
        self.supplier = MaterialSupplier.objects.create(
            code="PT01",
            name="Procurement supplier",
            account=supplier_account,
        )

    def _request(self, source_key="demand-1", quantity=10):
        result = generate_shortage_requests(
            [{
                "material_id": self.material.pk,
                "quantity": quantity,
                "source_type": "production_order",
                "source_key": source_key,
            }],
            location=self.location,
            user=self.user,
        )
        return result["request"]

    def _order(self, source_key="demand-1", quantity=10, price=100):
        request = self._request(source_key, quantity)
        line = request.lines.get()
        return approve_request(
            request,
            supplier=self.supplier,
            prices={line.pk: price},
            user=self.user,
        )

    def _attach(self, receipt):
        return create_attachment(
            SimpleUploadedFile("invoice.pdf", b"%PDF-1.7\ninvoice", content_type="application/pdf"),
            source_type="goods_receipt",
            source_id=receipt.pk,
            user=self.user,
        )

    def test_shortage_generation_is_idempotent_by_source_and_material(self):
        first = self._request()
        second = generate_shortage_requests(
            [{
                "material_id": self.material.pk,
                "quantity": 10,
                "source_type": "production_order",
                "source_key": "demand-1",
            }],
            location=self.location,
            user=self.user,
        )
        self.assertIsNone(second["request"])
        self.assertEqual(second["existing_lines"][0].request_id, first.pk)
        self.assertEqual(PurchaseRequestLine.objects.count(), 1)

    def test_partial_and_final_receipts_keep_material_and_create_separate_lots(self):
        order = self._order()
        line = order.lines.get()
        first = receive_order(
            order,
            [{"order_line_id": line.pk, "received_quantity": 4, "expected_quantity": 4, "unit_price": 100}],
            receipt_number="GR-1",
            invoice_number="INV-1",
            user=self.user,
        )
        self.assertFalse(first.is_final)
        self._attach(first)
        approve_goods_receipt(first, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_PARTIAL)

        second = receive_order(
            order,
            [{"order_line_id": line.pk, "received_quantity": 6, "expected_quantity": 6, "unit_price": 110,
              "price_variance_reason": "Supplier revision"}],
            receipt_number="GR-2",
            invoice_number="INV-2",
            user=self.user,
        )
        self.assertTrue(second.is_final)
        self._attach(second)
        approve_goods_receipt(second, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_RECEIVED)
        self.assertEqual(InventoryCostLayer.objects.filter(material=self.material).count(), 2)
        self.assertFalse(Material.objects.filter(pk=self.material.pk).get().is_deleted)

    def test_over_receipt_rolls_back_and_final_approval_requires_attachment(self):
        order = self._order(quantity=5)
        line = order.lines.get()
        with self.assertRaisesRegex(ValueError, "exceeds"):
            receive_order(
                order,
                [{"order_line_id": line.pk, "received_quantity": 6, "expected_quantity": 6, "unit_price": 100}],
                receipt_number="GR-X",
                invoice_number="INV-X",
                user=self.user,
            )
        self.assertEqual(GoodsReceipt.objects.count(), 0)
        receipt = receive_order(
            order,
            [{"order_line_id": line.pk, "received_quantity": 5, "expected_quantity": 5, "unit_price": 100}],
            receipt_number="GR-OK",
            invoice_number="INV-OK",
            user=self.user,
        )
        with self.assertRaisesRegex(ValueError, "invoice image"):
            approve_goods_receipt(receipt, user=self.user)
        self.assertEqual(InventoryTransaction.objects.count(), 0)

    def test_approval_has_one_idempotent_accounting_event_and_journal(self):
        order = self._order()
        line = order.lines.get()
        receipt = receive_order(
            order,
            [{"order_line_id": line.pk, "received_quantity": 10, "expected_quantity": 10, "unit_price": 100}],
            receipt_number="GR-A",
            invoice_number="INV-A",
            user=self.user,
        )
        self._attach(receipt)
        first = approve_goods_receipt(receipt, user=self.user)
        second = approve_goods_receipt(receipt, user=self.user)
        self.assertEqual(first.accounting_event_id, second.accounting_event_id)
        self.assertEqual(
            FinancialEvent.objects.filter(
                source_module="procurement", source_key=str(receipt.uuid)
            ).count(),
            1,
        )
        self.assertEqual(first.accounting_event.journal_id, first.purchase_invoice.journal_id)

    def test_api_permissions_and_shortage_to_order_workflow(self):
        denied = Client()
        denied.force_login(self.plain)
        self.assertEqual(denied.get("/api/procurement/requests/").status_code, 403)

        client = Client()
        client.force_login(self.user)
        response = client.post(
            "/api/procurement/shortages/generate/",
            data=json.dumps({
                "destination": {"kind": "warehouse", "warehouse_id": self.warehouse.pk},
                "requirements": [{
                    "material_id": self.material.pk,
                    "quantity": 3,
                    "source_type": "sale",
                    "source_key": "api-demand",
                }],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        request_uuid = response.json()["data"]["request"]["uuid"]
        request_line_id = response.json()["data"]["request"]["lines"][0]["id"]
        approved = client.post(
            f"/api/procurement/requests/{request_uuid}/approve/",
            data=json.dumps({
                "supplier_id": self.supplier.pk,
                "prices": {str(request_line_id): 125},
            }),
            content_type="application/json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(approved.json()["data"]["status"], "approved")
        order_uuid = approved.json()["data"]["uuid"]
        order_line_id = approved.json()["data"]["lines"][0]["id"]
        received = client.post(
            f"/api/procurement/orders/{order_uuid}/receive/",
            data=json.dumps({
                "receipt_number": "API-GR",
                "invoice_number": "API-INV",
                "lines": [{
                    "order_line_id": order_line_id,
                    "expected_quantity": 3,
                    "received_quantity": 3,
                    "unit_price": 125,
                }],
            }),
            content_type="application/json",
        )
        self.assertEqual(received.status_code, 201, received.content)
        receipt = received.json()["data"]
        uploaded = client.post(
            "/api/attachments/",
            data={
                "source_type": "goods_receipt",
                "source_id": receipt["id"],
                "file": SimpleUploadedFile(
                    "api-invoice.pdf",
                    b"%PDF-1.7\napi invoice",
                    content_type="application/pdf",
                ),
            },
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        finalized = client.post(
            f"/api/procurement/receipts/{receipt['uuid']}/approve/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(finalized.status_code, 200, finalized.content)
        self.assertEqual(finalized.json()["data"]["status"], "approved")
