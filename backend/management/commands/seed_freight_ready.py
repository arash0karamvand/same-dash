"""داده نمونه برای مانده اداری، تایید نهایی، فوریت ۷/۳ روز و ارسال به باربری."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from auth import roles
from auth.views import apply_user_access
from backend.models import Customer, Notification, Product, ProductCategory, ProductVariant, Sale, SaleLineItem, Seller
from logic.early_ship import confirm_factory_delivery_ready
from logic.membership import generate_membership_code
from logic.order_cycle import seed_order_cycle
from logic.order_queues import as_factory_order, migrate_office_to_factory_if_needed, migrate_sale_to_office_if_needed
from logic.role_definitions import seed_builtin_roles
from logic.sale_workflow import (
    STAGE_BRANCH_APPROVED,
    STAGE_IN_FREIGHT,
    STAGE_IN_PRODUCTION,
    STAGE_PRODUCTION_DONE,
)
from logic.seed_defaults import seed_system_defaults
from logic.sellers import ensure_seller_for_user

User = get_user_model()
PASSWORD = "Test@1404"

USERS = [
    ("demo_acct1", "پریسا رضایی", roles.ACCOUNTING_FINANCE, None),
    ("demo_acct2", "امیر موسوی", roles.ACCOUNTING_FINANCE, None),
    ("demo_sale01", "علی احمدی", roles.SALES_EXPERT, "branch_1"),
    ("demo_bs1", "حامد بی‌طرف", roles.BRANCH_SUPERVISOR, "branch_1"),
    ("demo_fact1", "رضا کارخانه", roles.FACTORY_SUPERVISOR, None),
    ("demo_freight1", "کریم باربری", roles.FREIGHT_SUPERVISOR, None),
]

INVOICE_PREFIX = "SEED-FR-"


class Command(BaseCommand):
    help = "Seed demo orders for office balance, final confirm, urgency colors, tickets and freight"

    def handle(self, *args, **options):
        seed_system_defaults()
        seed_builtin_roles()
        seed_order_cycle()

        users = self._ensure_users()
        products = self._ensure_products()
        factory_user = users["demo_fact1"]
        office_user = users["demo_acct1"]
        freight_user = users["demo_freight1"]
        branch_user = users["demo_bs1"]
        expert = users["demo_sale01"]

        self._clear_previous()
        customers = self._customers()
        created = self._create_orders(
            products=products,
            customers=customers,
            expert=expert,
            branch_user=branch_user,
            office_user=office_user,
            factory_user=factory_user,
            freight_user=freight_user,
        )
        self._print_guide(created)

    def _ensure_users(self):
        users = {}
        for username, full_name, role, branch in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@test.local"},
            )
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.is_active = True
            if created or not user.has_usable_password():
                user.set_password(PASSWORD)
            user.save()
            apply_user_access(user, role, branch)
            if role in (roles.SALES_EXPERT, roles.BRANCH_SUPERVISOR):
                seller = ensure_seller_for_user(user, branch=branch or "branch_1")
                seller.is_active = True
                seller.save()
            users[username] = user
        return users

    def _ensure_products(self):
        cat, _ = ProductCategory.objects.get_or_create(
            name="مبلمان تست",
            defaults={"color": "#6366f1", "icon": "🛋️", "sort_order": 0},
        )
        product, _ = Product.objects.get_or_create(
            sku="SEED-FR-LUNA",
            defaults={
                "name": "مبل راحتی لونا",
                "category": cat,
                "fabric": "مخمل",
                "default_price": Decimal("18500000"),
                "is_active": True,
            },
        )
        ProductVariant.objects.get_or_create(
            product=product,
            color_name="کرم",
            defaults={"color_hex": "#f5f5dc", "price": product.default_price, "is_active": True},
        )
        return [product]

    def _clear_previous(self):
        sales = list(Sale.all_objects.filter(invoice_number__startswith=INVOICE_PREFIX))
        sale_ids = [sale.pk for sale in sales]
        if sale_ids:
            Notification.objects.filter(payload__sale_id__in=sale_ids).delete()
            SaleLineItem.objects.filter(sale_id__in=sale_ids).delete()
            Sale.all_objects.filter(pk__in=sale_ids).delete()
        Customer.objects.filter(phone__startswith="09129990").delete()

    def _customers(self):
        specs = [
            ("09129990001", "نیما مانده‌دار", "تهران، نیاوران"),
            ("09129990002", "سحر تسویه‌شده", "تهران، پاسداران"),
            ("09129990003", "آرش نارنجی", "کرج، کمرد"),
            ("09129990004", "لیلا قرمز", "تهران، جردن"),
            ("09129990005", "کیان دور", "تهران، سعادت‌آباد"),
            ("09129990006", "مریم آماده", "تهران، ونک"),
            ("09129990007", "بهراد تیکت", "تهران، فرمانیه"),
            ("09129990008", "نگار زودرس", "تهران، الهیه"),
            ("09129990009", "سامان امروز", "تهران، تجریش"),
        ]
        rows = []
        for phone, name, address in specs:
            customer, _ = Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "full_name": name,
                    "membership_code": generate_membership_code(),
                    "address": address,
                },
            )
            customer.full_name = name
            customer.address = address
            customer.save(update_fields=["full_name", "address", "updated_at"])
            rows.append(customer)
        return rows

    def _create_orders(self, **actors):
        today = timezone.localdate()
        now = timezone.now()
        product = actors["products"][0]
        variant = product.variants.filter(is_active=True).first()
        specs = [
            {
                "invoice": f"{INVOICE_PREFIX}OFFICE-BAL",
                "customer": actors["customers"][0],
                "stage": STAGE_BRANCH_APPROVED,
                "final": Decimal("18000000"),
                "paid": Decimal("8000000"),
                "lead_days": 8,
                "remaining_days": 5,
                "where": "اداری → تایید سفارش",
                "see": "مبلغ ۱۸ میلیون، مانده ۱۰ میلیون",
            },
            {
                "invoice": f"{INVOICE_PREFIX}OFFICE-ZERO",
                "customer": actors["customers"][1],
                "stage": STAGE_BRANCH_APPROVED,
                "final": Decimal("9500000"),
                "paid": Decimal("9500000"),
                "lead_days": 6,
                "remaining_days": 4,
                "where": "اداری → تایید سفارش",
                "see": "مانده صفر کنار مبلغ",
            },
            {
                "invoice": f"{INVOICE_PREFIX}ORANGE",
                "customer": actors["customers"][2],
                "stage": STAGE_PRODUCTION_DONE,
                "final": Decimal("12500000"),
                "paid": Decimal("12500000"),
                "lead_days": 9,
                "remaining_days": 6,
                "where": "کارخانه → ساخته‌شده‌ها",
                "see": "ردیف نارنجی — ۶ روز مانده، دکمه تایید نهایی",
            },
            {
                "invoice": f"{INVOICE_PREFIX}RED",
                "customer": actors["customers"][3],
                "stage": STAGE_PRODUCTION_DONE,
                "final": Decimal("14200000"),
                "paid": Decimal("14200000"),
                "lead_days": 8,
                "remaining_days": 2,
                "where": "کارخانه → ساخته‌شده‌ها",
                "see": "ردیف قرمز — ۲ روز مانده",
            },
            {
                "invoice": f"{INVOICE_PREFIX}FAR",
                "customer": actors["customers"][4],
                "stage": STAGE_PRODUCTION_DONE,
                "final": Decimal("11000000"),
                "paid": Decimal("11000000"),
                "lead_days": 16,
                "remaining_days": 12,
                "where": "کارخانه → ساخته‌شده‌ها",
                "see": "رنگ عادی — ۱۲ روز مانده",
            },
            {
                "invoice": f"{INVOICE_PREFIX}READY",
                "customer": actors["customers"][5],
                "stage": STAGE_PRODUCTION_DONE,
                "final": Decimal("16700000"),
                "paid": Decimal("16700000"),
                "lead_days": 8,
                "remaining_days": 4,
                "confirm": True,
                "where": "کارخانه → ساخته‌شده‌ها",
                "see": "رنگ آماده تحویل + دکمه ارسال به باربری",
            },
            {
                "invoice": f"{INVOICE_PREFIX}TICKET",
                "customer": actors["customers"][6],
                "stage": STAGE_PRODUCTION_DONE,
                "final": Decimal("21000000"),
                "paid": Decimal("21000000"),
                "lead_days": 14,
                "remaining_days": 5,
                "confirm": True,
                "where": "اعلان‌ها + ساخته‌شده‌ها",
                "see": "تیکت تعیین تکلیف؛ ارسال قفل تا تاریخ اداری",
            },
            {
                "invoice": f"{INVOICE_PREFIX}EARLY",
                "customer": actors["customers"][7],
                "stage": STAGE_IN_FREIGHT,
                "final": Decimal("19800000"),
                "paid": Decimal("19800000"),
                "lead_days": 9,
                "remaining_days": 4,
                "shipped_early": True,
                "where": "کارخانه → باربری",
                "see": "برچسب ارسال زودتر از موعد",
            },
            {
                "invoice": f"{INVOICE_PREFIX}TODAY",
                "customer": actors["customers"][8],
                "stage": STAGE_IN_FREIGHT,
                "final": Decimal("7300000"),
                "paid": Decimal("7300000"),
                "lead_days": 7,
                "remaining_days": 0,
                "shipped_early": False,
                "where": "کارخانه → باربری",
                "see": "صف ارسال به مشتری — تحویل امروز، دکمه تحویل شد",
            },
        ]
        created = []
        for spec in specs:
            created.append(self._make_sale(spec, product, variant, actors, today, now))
        return created

    @transaction.atomic
    def _make_sale(self, spec, product, variant, actors, today, now):
        remaining = spec["remaining_days"]
        lead = spec["lead_days"]
        sold_at = now - timedelta(days=max(lead - remaining, 1), hours=3)
        delivery = today + timedelta(days=remaining)
        qty = 1
        unit = spec["final"]
        sale = Sale.objects.create(
            customer=spec["customer"],
            amount=unit,
            discount_type="amount",
            discount_value=0,
            discount=0,
            final_amount=unit,
            paid_amount=spec["paid"],
            payment_status="paid" if spec["paid"] >= unit else ("installment" if spec["paid"] > 0 else "unpaid"),
            payment_method="cash",
            order_kind=Sale.ORDER_KIND_NORMAL,
            order_status=(
                Sale.ORDER_STATUS_PENDING
                if spec["stage"] == STAGE_BRANCH_APPROVED
                else Sale.ORDER_STATUS_CONFIRMED
            ),
            workflow_stage_id=spec["stage"],
            fulfillment_route=Sale.FULFILLMENT_ROUTE_FACTORY,
            delivery_date=delivery,
            recorded_by=actors["expert"],
            branch_id="branch_1",
            seller=Seller.objects.filter(user=actors["expert"]).first(),
            sold_at=sold_at,
            invoice_number=spec["invoice"],
            description=spec["see"],
            branch_approved_at=sold_at + timedelta(hours=2),
            branch_approved_by=actors["branch_user"],
            office_released_at=sold_at + timedelta(hours=3),
        )
        if spec["stage"] != STAGE_BRANCH_APPROVED:
            sale.accounting_approved_at = sold_at + timedelta(hours=6)
            sale.accounting_approved_by = actors["office_user"]
            sale.factory_released_at = sold_at + timedelta(hours=6)
            sale.factory_received_at = sold_at + timedelta(hours=12)
            sale.factory_received_by = actors["factory_user"]
        if spec["stage"] in {STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT}:
            sale.production_done_at = sold_at + timedelta(days=2)
            sale.workflow_stage_id = STAGE_IN_PRODUCTION
        sale.save()
        SaleLineItem.objects.create(
            sale=sale,
            product=product,
            variant=variant,
            product_name=product.name,
            product_model=product.product_model or "",
            fabric=product.fabric or "",
            color_name=variant.color_name if variant else "",
            color_hex=variant.color_hex if variant else "",
            quantity=qty,
            unit_price=unit,
            line_total=unit,
        )
        office = migrate_sale_to_office_if_needed(sale)
        if office:
            migrate_office_to_factory_if_needed(office)
        sale.refresh_from_db()
        if spec["stage"] in {STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT}:
            factory = as_factory_order(sale)
            factory.workflow_stage_id = STAGE_PRODUCTION_DONE
            factory.production_done_at = sold_at + timedelta(days=2)
            factory.save(update_fields=["workflow_stage", "production_done_at"])
            sale.refresh_from_db()
            if spec.get("confirm"):
                confirm_factory_delivery_ready(as_factory_order(sale), actors["factory_user"])
                sale.refresh_from_db()
            if spec["stage"] == STAGE_IN_FREIGHT:
                sale.workflow_stage_id = STAGE_IN_FREIGHT
                sale.freight_received_at = timezone.now()
                sale.freight_received_by = actors["freight_user"]
                sale.shipped_early = bool(spec.get("shipped_early"))
                sale.delivery_ready_at = sale.delivery_ready_at or timezone.now()
                sale.delivery_ready_by = sale.delivery_ready_by or actors["factory_user"]
                sale.save(
                    update_fields=[
                        "workflow_stage",
                        "freight_received_at",
                        "freight_received_by",
                        "shipped_early",
                        "delivery_ready_at",
                        "delivery_ready_by",
                    ]
                )
        sale.refresh_from_db()
        spec["sale"] = sale
        spec["delivery"] = sale.delivery_date
        spec["balance"] = int(sale.final_amount - sale.paid_amount)
        return spec

    def _print_guide(self, created):
        self.stdout.write(self.style.SUCCESS("\n=== seed تایید نهایی / مانده / باربری ==="))
        self.stdout.write(f"رمز همه حساب‌های دمو: {PASSWORD}")
        self.stdout.write("ورود پیشنهادی:")
        self.stdout.write("  demo_acct1     اداری — تایید سفارش و تیکت")
        self.stdout.write("  demo_sale01    فروشگاه — تیکت مدیریت مشتریان")
        self.stdout.write("  demo_fact1     کارخانه — ساخته‌شده‌ها")
        self.stdout.write("  demo_freight1  باربری")
        self.stdout.write("")
        self.stdout.write(f"{'فاکتور':<22} {'صفحه':<28} {'چی می‌بینید'}")
        self.stdout.write("-" * 90)
        for spec in created:
            sale = spec["sale"]
            self.stdout.write(
                f"{sale.invoice_number:<22} {spec['where']:<28} {spec['see']}"
            )
        tickets = Notification.objects.filter(
            payload__purpose="early_ship_disposition",
            payload__invoice_number=f"{INVOICE_PREFIX}TICKET",
        )
        self.stdout.write("")
        self.stdout.write(f"تیکت/مسئولیت ساخته‌شده: {tickets.count()} (باید ۲ باشد: تیکت + مسئولیت)")
        for note in tickets:
            self.stdout.write(f"  - {note.get_action_type_display() if hasattr(note, 'get_action_type_display') else note.action_type}: {note.title}")
