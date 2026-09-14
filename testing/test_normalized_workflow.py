from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from api.serializers import factory_order_to_dict, office_order_to_dict
from backend.models import (
    Customer,
    FactoryOrder,
    InventoryTransaction,
    Material,
    OfficeOrder,
    OrderTransition,
    Product,
    ProductMaterial,
    Sale,
    SaleLineItem,
)
from logic.installments import create_installments
from logic.materials import deduct_materials_for_factory_order, restore_materials_for_factory_order
from logic.order_queues import create_factory_order_from_office, create_office_order_from_sale
from logic.sale_workflow import receive_factory_order


class NormalizedWorkflowTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="workflow")
        self.customer = Customer.objects.create(full_name="مشتری", phone="09120000123")
        self.sale = Sale.objects.create(
            customer=self.customer,
            branch_id="branch_1",
            workflow_stage_id=Sale.WORKFLOW_STAGE_PENDING_BRANCH,
            amount=1000,
            final_amount=1000,
            accounting_mode=Sale.ACCOUNTING_MODE_MANUAL,
        )

    def test_proxies_share_one_row_and_transitions_are_recorded(self):
        office = create_office_order_from_sale(self.sale, self.user)
        office_payload = office_order_to_dict(office, include_lines=True)
        factory = create_factory_order_from_office(office, self.user)
        factory = receive_factory_order(factory, self.user)
        factory_payload = factory_order_to_dict(factory, include_lines=True)

        self.assertEqual(Sale.objects.filter(pk=self.sale.pk).count(), 1)
        self.assertEqual(office.pk, self.sale.pk)
        self.assertEqual(factory.pk, self.sale.pk)
        self.assertEqual(factory.workflow_stage_id, Sale.WORKFLOW_STAGE_IN_PRODUCTION)
        self.assertEqual(OrderTransition.objects.filter(order_id=self.sale.pk).count(), 3)
        self.assertEqual(office_payload["source_sale_id"], self.sale.pk)
        self.assertEqual(office_payload["branch"], "branch_1")
        self.assertEqual(factory_payload["source_office_order_id"], self.sale.pk)
        self.assertEqual(factory_payload["workflow_stage"], Sale.WORKFLOW_STAGE_IN_PRODUCTION)

    def test_installments_are_visible_through_office_proxy(self):
        create_installments(
            self.sale,
            [{"amount": 1000, "due_date": date.today(), "payment_method": "cash"}],
        )
        office = create_office_order_from_sale(self.sale, self.user)
        self.assertEqual(office.installments.count(), 1)
        self.assertEqual(office.installments.first().sale_id, self.sale.pk)

    def test_factory_payload_query_count_is_bounded(self):
        product = Product.objects.create(name="محصول", default_price=1000)
        SaleLineItem.objects.create(
            sale=self.sale,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price=1000,
            line_total=1000,
        )
        create_office_order_from_sale(self.sale, self.user)
        create_factory_order_from_office(
            OfficeOrder.all_objects.get(pk=self.sale.pk),
            self.user,
        )

        with CaptureQueriesContext(connection) as queries:
            factory = (
                FactoryOrder.objects.select_related("customer", "branch")
                .prefetch_related("line_items")
                .get(pk=self.sale.pk)
            )
            factory_order_to_dict(factory, include_lines=True, user=None)

        self.assertLessEqual(len(queries), 8)

    @patch("logic.material_accounting.post_factory_material_consumption")
    @patch("logic.material_accounting.reverse_factory_material_consumption")
    def test_material_consumption_is_append_only(self, _reverse, _post):
        material = Material.objects.create(
            name="پارچه",
            unit_cost=10,
            approval_status=Material.APPROVAL_APPROVED,
            is_active=True,
        )
        InventoryTransaction.objects.create(
            material=material,
            quantity=10,
            unit_cost=10,
            reason="initial_stock",
        )
        product = Product.objects.create(name="محصول", default_price=1000)
        ProductMaterial.objects.create(product=product, material=material, quantity=2)
        SaleLineItem.objects.create(
            sale=self.sale,
            product=product,
            product_name=product.name,
            quantity=2,
            unit_price=500,
            line_total=1000,
        )
        factory = FactoryOrder.all_objects.get(pk=self.sale.pk)

        deduct_materials_for_factory_order(factory)
        material.refresh_from_db()
        self.assertEqual(material.stock, Decimal("6"))
        restore_materials_for_factory_order(factory)
        material.refresh_from_db()
        self.assertEqual(material.stock, Decimal("10"))
        self.assertEqual(material.inventory_movements.count(), 3)
