"""Seed visible factory-product, administrative-costing and order-flow scenarios."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from auth.permissions import VIEW_DASHBOARD, can_view_costs, has_permission
from backend.models import (
    BOMLine,
    BOMVersion,
    Branch,
    Customer,
    DashboardWidget,
    FurnitureWorkset,
    FurnitureWorksetPiece,
    Material,
    Product,
    ProductMaterial,
    ProductVariant,
    ProductionOrder,
    ProductionRun,
    Sale,
    SaleLineItem,
)
from logic.products import apply_admin_cost_pricing
from logic.stock_locations import default_warehouse


PREFIX = "DEMO200"
STAGE_BUCKETS = [
    ("factory_product", "فقط محصول کارخانه"),
    ("office_priced", "قیمت‌گذاری‌شده توسط اداری"),
    *Sale.WORKFLOW_STAGE_CHOICES,
]


class Command(BaseCommand):
    help = "Create 200 tagged product/material/order scenarios across the complete flow"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)
        parser.add_argument("--username")
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        if count < 1 or count > 2000:
            raise CommandError("count must be between 1 and 2000")
        actor = self._actor(options.get("username"))
        if options["reset"]:
            self._cleanup()

        branch, _ = Branch.objects.get_or_create(
            code="branch_1", defaults={"label": "شعبه نمونه", "is_active": True}
        )
        warehouse = default_warehouse()
        workset = self._workset()
        created = {key: 0 for key, _label in STAGE_BUCKETS}

        for index in range(1, count + 1):
            bucket, _label = STAGE_BUCKETS[(index - 1) % len(STAGE_BUCKETS)]
            material = self._material(index)
            product, variant = self._product(index, material, workset, bucket)
            created[bucket] += 1
            if bucket in {"factory_product", "office_priced"}:
                continue
            sale = self._sale(index, actor, branch, product, variant, bucket)
            if bucket in {
                Sale.WORKFLOW_STAGE_IN_PRODUCTION,
                Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
                Sale.WORKFLOW_STAGE_COMPLETED,
            }:
                self._production(index, actor, warehouse, sale, product, variant, material, bucket)

        self._widgets(actor)
        self.stdout.write(self.style.SUCCESS(f"{count} tagged demo scenarios are ready."))
        self.stdout.write(f"Prefix: {PREFIX}")
        self.stdout.write(f"Dashboard user: {actor.username}")
        for key, _label in STAGE_BUCKETS:
            self.stdout.write(f"  {key}: {created[key]}")
        self.stdout.write(
            f"Totals: products: {Product.objects.filter(sku__startswith=PREFIX).count()}, "
            f"materials: {Material.objects.filter(sku__startswith=PREFIX).count()}, "
            f"orders: {Sale.objects.filter(description__startswith=PREFIX).count()}, "
            f"production runs: {ProductionRun.objects.filter(product__sku__startswith=PREFIX).count()}"
        )

    def _actor(self, username):
        users = get_user_model().objects
        if username:
            actor = users.filter(username=username, is_active=True).first()
            if not actor:
                raise CommandError(f"Active user not found: {username}")
            return actor
        actor = users.filter(is_superuser=True, is_active=True).order_by("id").first()
        if not actor:
            actor = users.filter(is_active=True).order_by("id").first()
        if not actor:
            raise CommandError("No active user exists; create an administrative user first.")
        return actor

    def _workset(self):
        workset, _ = FurnitureWorkset.objects.get_or_create(
            name=f"{PREFIX} — دست آزمایشی",
            defaults={"design_style": "modern", "seat_count": 8, "is_active": True},
        )
        FurnitureWorksetPiece.objects.get_or_create(
            workset=workset,
            piece_kind="sofa_3",
            arm_style="two",
            defaults={"quantity": 1, "sort_order": 0},
        )
        FurnitureWorksetPiece.objects.get_or_create(
            workset=workset,
            piece_kind="armchair",
            arm_style="none",
            defaults={"quantity": 2, "sort_order": 1},
        )
        return workset

    def _material(self, index):
        material, _ = Material.objects.update_or_create(
            sku=f"{PREFIX}-MAT-{index:04d}",
            defaults={
                "name": f"{PREFIX} متریال {index:04d}",
                "usage_kind": Material.USAGE_FABRIC if index % 2 else Material.USAGE_WOOD,
                "unit": "متر",
                "unit_cost": Decimal(100000 + index * 2500),
                "is_active": True,
                "approval_status": Material.APPROVAL_APPROVED,
            },
        )
        return material

    def _product(self, index, material, workset, bucket):
        product, _ = Product.objects.update_or_create(
            sku=f"{PREFIX}-PRD-{index:04d}",
            defaults={
                "name": f"{PREFIX} محصول {index:04d} — {dict(STAGE_BUCKETS)[bucket]}",
                "product_model": workset.name,
                "furniture_workset": workset,
                "suite_config": [
                    {
                        "piece_kind": "sofa_3",
                        "arm_style": "two",
                        "piece_label": "سه‌نفره دو دسته",
                        "quantity": 1,
                        "needs_paint": True,
                        "pipeline_end": "upholstery",
                    },
                    {
                        "piece_kind": "armchair",
                        "arm_style": "none",
                        "piece_label": "تک‌نفره بدون دسته",
                        "quantity": 2,
                        "needs_paint": True,
                        "pipeline_end": "upholstery",
                    },
                ],
                "default_price": 0,
                "is_active": True,
            },
        )
        ProductMaterial.objects.update_or_create(
            product=product,
            material=material,
            defaults={"quantity": Decimal("3.000"), "sort_order": 0},
        )
        if bucket != "factory_product":
            pricing = {
                "profit_mode": Product.PROFIT_FIXED if index % 2 == 0 else Product.PROFIT_PERCENT,
                "target_margin_percent": Decimal(20 + index % 16),
                "target_profit_amount": Decimal(1500000 + index * 10000),
                "cost_override": (
                    Decimal(material.unit_cost) * Decimal("3.15") if index % 3 == 0 else None
                ),
            }
            apply_admin_cost_pricing(product, pricing)
            product.save()
        variant, _ = ProductVariant.objects.update_or_create(
            product=product,
            color_name=f"رنگ نمونه {index % 12 + 1}",
            defaults={
                "color_hex": f"#{(index * 7919) % 0xFFFFFF:06x}",
                "sku": f"{PREFIX}-VAR-{index:04d}",
                "price": product.default_price,
                "is_active": True,
            },
        )
        return product, variant

    def _sale(self, index, actor, branch, product, variant, stage):
        customer, _ = Customer.objects.get_or_create(
            phone=f"0908{index:07d}",
            defaults={"full_name": f"{PREFIX} مشتری {index:04d}"},
        )
        now = timezone.now() - timedelta(days=index % 30)
        sale, _ = Sale.objects.update_or_create(
            branch=branch,
            invoice_number=f"{PREFIX}-{index:04d}",
            defaults={
                "customer": customer,
                "amount": product.default_price,
                "final_amount": product.default_price,
                "paid_amount": product.default_price if stage == Sale.WORKFLOW_STAGE_COMPLETED else 0,
                "sold_at": now,
                "description": f"{PREFIX} — {dict(STAGE_BUCKETS)[stage]} — رکورد {index:04d}",
                "recorded_by": actor,
                "workflow_stage_id": stage,
                "accounting_mode_ref_id": Sale.ACCOUNTING_MODE_MANUAL,
                "payment_status_ref_id": (
                    Sale.PAYMENT_STATUS_CHOICES[0][0]
                    if stage == Sale.WORKFLOW_STAGE_COMPLETED
                    else Sale.PAYMENT_STATUS_CHOICES[1][0]
                ),
                "payment_method_ref_id": Sale.PAYMENT_METHOD_CHOICES[0][0],
                "order_status_ref_id": Sale.ORDER_STATUS_CONFIRMED,
                "order_kind_ref_id": Sale.ORDER_KIND_NORMAL,
                "seat_count": 8,
            },
        )
        SaleLineItem.objects.update_or_create(
            sale=sale,
            product=product,
            defaults={
                "variant": variant,
                "furniture_workset": product.furniture_workset,
                "product_name": product.name,
                "product_model": product.product_model,
                "quantity": 1,
                "unit_price": product.default_price,
                "line_total": product.default_price,
                "workset_config": {
                    "sale_mode": "full_set",
                    "furniture_workset_id": product.furniture_workset_id,
                    "pieces": product.suite_config,
                },
            },
        )
        return sale

    def _production(self, index, actor, warehouse, sale, product, variant, material, stage):
        order, _ = ProductionOrder.objects.update_or_create(
            sale=sale,
            defaults={
                "invoice_number": sale.invoice_number,
                "customer_name": sale.customer.full_name,
                "branch_name": sale.branch.label,
                "delivery_date": timezone.localdate() + timedelta(days=14),
                "product_name": product.name,
                "product_model": product.product_model,
                "created_by": actor,
                "status": (
                    ProductionOrder.STATUS_COMPLETED
                    if stage in {Sale.WORKFLOW_STAGE_PRODUCTION_DONE, Sale.WORKFLOW_STAGE_COMPLETED}
                    else ProductionOrder.STATUS_IN_PRODUCTION
                ),
            },
        )
        bom, _ = BOMVersion.objects.get_or_create(
            product=product,
            version=1,
            defaults={
                "status": BOMVersion.STATUS_DRAFT,
                "source_snapshot": {"seed": PREFIX},
                "published_by": actor,
            },
        )
        if bom.status == BOMVersion.STATUS_DRAFT:
            BOMLine.objects.get_or_create(
                bom_version=bom,
                material=material,
                defaults={
                    "quantity": Decimal("3.000"),
                    "source_kind": BOMLine.SOURCE_PRODUCT,
                    "source_reference": PREFIX,
                },
            )
            bom.status = BOMVersion.STATUS_PUBLISHED
            bom.published_at = timezone.now()
            bom.save(update_fields=["status", "published_at"])
        material_cost = Decimal(material.unit_cost) * Decimal(3)
        overhead = (material_cost * Decimal("0.15")).quantize(Decimal("1"))
        run_status = (
            ProductionRun.STATUS_COMPLETED
            if stage in {Sale.WORKFLOW_STAGE_PRODUCTION_DONE, Sale.WORKFLOW_STAGE_COMPLETED}
            else ProductionRun.STATUS_IN_PROGRESS
        )
        ProductionRun.objects.update_or_create(
            production_order=order,
            defaults={
                "sale": sale,
                "product": product,
                "variant": variant,
                "bom_version": bom,
                "quantity": 1,
                "warehouse": warehouse,
                "status": run_status,
                "actual_material_cost": material_cost,
                "overhead_cost": overhead,
                "total_cost": material_cost + overhead,
                "started_at": timezone.now() - timedelta(days=2),
                "completed_at": timezone.now() if run_status == ProductionRun.STATUS_COMPLETED else None,
                "created_by": actor,
                "completed_by": actor if run_status == ProductionRun.STATUS_COMPLETED else None,
            },
        )

    def _widgets(self, actor):
        specs = [
            ("آزمایش ۲۰۰ رکورد — ارزش موجودی", "stat_card", "material_inventory_value"),
            ("آزمایش ۲۰۰ رکورد — بهای تولید", "stat_card", "production_cost_summary"),
            ("آزمایش ۲۰۰ رکورد — روند بهای تولید", "chart_line", "production_cost_trend"),
        ]
        users = [actor]
        for user in get_user_model().objects.filter(is_active=True):
            if user.pk != actor.pk and has_permission(user, VIEW_DASHBOARD) and can_view_costs(user):
                users.append(user)
        for user in users:
            for position, (title, widget_type, metric) in enumerate(specs, start=90):
                DashboardWidget.objects.update_or_create(
                    user=user,
                    title=title,
                    defaults={
                        "widget_type": widget_type,
                        "config": {"metric": metric, "time_range": "month"},
                        "position": position,
                        "size": "medium" if widget_type == "stat_card" else "wide",
                    },
                )

    def _cleanup(self):
        product_ids = list(
            Product.objects.filter(sku__startswith=PREFIX).values_list("id", flat=True)
        )
        sale_ids = list(
            Sale.objects.filter(description__startswith=PREFIX).values_list("id", flat=True)
        )
        ProductionRun.objects.filter(product_id__in=product_ids).delete()
        ProductionOrder.objects.filter(sale_id__in=sale_ids).delete()
        bom_lines = BOMLine.objects.filter(bom_version__product_id__in=product_ids)
        if bom_lines.exists():
            # Demo cleanup is the only intentional hard-delete path for tagged,
            # generated append-only rows.
            bom_lines._raw_delete(bom_lines.db)
        BOMVersion.objects.filter(product_id__in=product_ids).delete()
        Sale.objects.filter(id__in=sale_ids).delete()
        Product.objects.filter(id__in=product_ids).delete()
        Material.objects.filter(sku__startswith=f"{PREFIX}-MAT-").delete()
        Customer.objects.filter(full_name__startswith=f"{PREFIX} مشتری").delete()
        FurnitureWorkset.objects.filter(name=f"{PREFIX} — دست آزمایشی").delete()
