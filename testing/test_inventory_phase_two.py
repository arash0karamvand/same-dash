import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from backend.models import (
    DocumentAttachment,
    InventoryAllocation,
    InventoryConsumption,
    InventoryCostLayer,
    InventoryReservation,
    InventoryTransaction,
    Material,
)
from logic.document_attachments import create_attachment, validate_upload
from logic.inventory_costing import (
    availability,
    consume_stock,
    receive_stock,
    release_reservation,
    reserve_stock,
)
from logic.stock_locations import ensure_central_warehouse


class InventoryPhaseTwoTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.user = get_user_model().objects.create_superuser(
            username="inventory-admin",
            email="inventory@example.test",
            password="testpass123",
        )
        self.material = Material.objects.create(
            name="FIFO material",
            unit_cost=100,
            valuation_method=Material.VALUATION_FIFO,
        )
        self.warehouse = ensure_central_warehouse()
        self.location = {
            "kind": InventoryTransaction.LOCATION_WAREHOUSE,
            "warehouse": self.warehouse,
            "warehouse_id": self.warehouse.pk,
            "branch": None,
        }

    def _receive(self, quantity, cost):
        return receive_stock(
            self.material,
            quantity,
            cost,
            location=self.location,
            recorded_by=self.user,
        )

    def test_fifo_persists_ten_from_first_and_five_from_second(self):
        self._receive(10, 100)
        self._receive(10, 200)

        result = consume_stock(
            self.material,
            15,
            location=self.location,
            user=self.user,
            reference="production:1",
        )

        self.assertEqual(
            [row["quantity"] for row in result["allocations"]],
            [Decimal("10"), Decimal("5")],
        )
        self.assertEqual(result["total_cost"], Decimal("2000"))
        self.assertEqual(
            list(
                InventoryCostLayer.objects.order_by("id").values_list(
                    "qty_remaining", flat=True
                )
            ),
            [Decimal("0"), Decimal("5")],
        )
        self.assertEqual(result["consumption"].allocations.count(), 2)

    def test_shortage_rejects_without_mutation(self):
        self._receive(10, 100)
        layer = InventoryCostLayer.objects.get()
        movements = InventoryTransaction.objects.count()

        with self.assertRaisesRegex(ValueError, "shortage"):
            consume_stock(self.material, 11, location=self.location, user=self.user)

        layer.refresh_from_db()
        self.assertEqual(layer.qty_remaining, Decimal("10"))
        self.assertEqual(InventoryTransaction.objects.count(), movements)
        self.assertEqual(InventoryConsumption.objects.count(), 0)

    def test_override_requires_reason_and_authorized_user(self):
        self._receive(10, 100)
        second_move = self._receive(10, 200)
        second = InventoryCostLayer.objects.get(source_transaction=second_move)
        override = [{"layer_id": second.pk, "quantity": 5}]

        with self.assertRaisesRegex(ValueError, "reason"):
            consume_stock(
                self.material,
                5,
                location=self.location,
                override_layers=override,
                user=self.user,
            )

        plain = get_user_model().objects.create_user(username="plain", password="testpass123")
        with self.assertRaises(PermissionDenied):
            consume_stock(
                self.material,
                5,
                location=self.location,
                override_layers=override,
                override_reason="Use inspected lot",
                user=plain,
            )

        result = consume_stock(
            self.material,
            5,
            location=self.location,
            override_layers=override,
            override_reason="Use inspected lot",
            user=self.user,
        )
        self.assertEqual(result["allocations"][0]["layer_id"], second.pk)
        self.assertEqual(result["consumption"].overridden_by, self.user)

    def test_reserve_and_release_changes_available_quantity(self):
        self._receive(10, 100)
        reservation = reserve_stock(
            self.material,
            4,
            location=self.location,
            user=self.user,
        )
        self.assertEqual(availability(self.material, location=self.location)["available"], Decimal("6"))

        release_reservation(reservation, user=self.user, reason="Order cancelled")
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, InventoryReservation.STATUS_RELEASED)
        self.assertEqual(availability(self.material, location=self.location)["available"], Decimal("10"))

    def test_movement_consumption_and_allocation_are_immutable(self):
        self._receive(10, 100)
        result = consume_stock(self.material, 2, location=self.location, user=self.user)
        movement = result["movement"]
        consumption = result["consumption"]
        allocation = InventoryAllocation.objects.get(consumption=consumption)

        movement.quantity = -3
        with self.assertRaises(ValueError):
            movement.save()
        with self.assertRaises(ValueError):
            InventoryTransaction.objects.filter(pk=movement.pk).update(quantity=-3)
        with self.assertRaises(ValueError):
            consumption.delete()
        with self.assertRaises(ValueError):
            InventoryAllocation.objects.filter(pk=allocation.pk).delete()

    def test_attachment_validation_and_explicit_source(self):
        valid = SimpleUploadedFile(
            "invoice.pdf",
            b"%PDF-1.7\nvalid",
            content_type="application/pdf",
        )
        attachment = create_attachment(
            valid,
            source_type="inventory_transaction",
            source_id=self._receive(1, 100).pk,
            user=self.user,
        )
        self.assertIsInstance(attachment, DocumentAttachment)
        self.assertIsNotNone(attachment.inventory_transaction_id)

        invalid = SimpleUploadedFile(
            "fake.pdf",
            b"not a pdf",
            content_type="application/pdf",
        )
        with self.assertRaisesRegex(ValueError, "signature"):
            validate_upload(invalid)
