"""بارگذاری داده تست در MySQL — نقش‌های سازمانی + صدها سفارش در همه مراحل."""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auth import roles
from auth.roles import ROLE_LABELS
from auth.views import apply_user_access, ensure_staff_profile
from backend.models import (
    Customer,
    OrgRank,
    Product,
    ProductCategory,
    ProductVariant,
    Sale,
    SaleLineItem,
    Seller,
    StaffAttendance,
)
from logic.membership import generate_membership_code
from logic.role_definitions import seed_builtin_roles
from logic.sale_workflow import (
    STAGE_ACCOUNTING_APPROVED,
    STAGE_BRANCH_APPROVED,
    STAGE_COMPLETED,
    STAGE_IN_FREIGHT,
    STAGE_IN_PRODUCTION,
    STAGE_PENDING_BRANCH,
    STAGE_PRODUCTION_DONE,
)
from logic.sellers import ensure_seller_for_user

User = get_user_model()

PASSWORD = "Test@1404"
BRANCHES = ["branch_1", "branch_2"]
CUSTOMER_COUNT = 100
SALE_COUNT = 300

STAGE_WEIGHTS = [
    (STAGE_PENDING_BRANCH, 50),
    (STAGE_BRANCH_APPROVED, 45),
    (STAGE_ACCOUNTING_APPROVED, 40),
    (STAGE_IN_PRODUCTION, 35),
    (STAGE_PRODUCTION_DONE, 35),
    (STAGE_IN_FREIGHT, 30),
    (STAGE_COMPLETED, 65),
]

FIRST_NAMES = [
    "علی", "رضا", "سارا", "مینا", "حسین", "فاطمه", "امیر", "نگار",
    "مهدی", "زهرا", "کامران", "لیلا", "پویا", "نرگس", "سینا", "مریم",
    "بهنام", "شیما", "آرمان", "پریسا",
]
LAST_NAMES = [
    "احمدی", "محمدی", "کریمی", "حسینی", "رضایی", "جعفری", "موسوی", "قاسمی",
    "نوری", "صادقی", "اکبری", "رحیمی", "زارعی", "باقری", "ملکی", "شریفی",
]
PRODUCT_SPECS = [
    ("مبل راحتی لونا", "LUNA-01", "مخمل", 18_500_000),
    ("مبل سه‌نفره آرتا", "ARTA-03", "چرم", 24_000_000),
    ("صندلی اداری ارگون", "ERG-12", "پارچه", 4_200_000),
    ("میز ناهارخوری ونیز", "VEN-08", "چوب راش", 9_800_000),
    ("کمد دیواری آلفا", "ALF-22", "MDF", 12_500_000),
    ("تخت خواب دو نفره رویال", "ROY-05", "چوب بلوط", 16_700_000),
    ("بوفه پذیرایی مدرن", "MOD-11", "چوب", 7_300_000),
    ("مبلمان گوشه ویستا", "VIS-09", "پارچه", 21_000_000),
    ("جاکفشی مدرن", "SHO-15", "MDF", 3_800_000),
    ("میز تلویزیون مینیمال", "TV-07", "چوب", 5_600_000),
]

# نقش‌های قابل تست — رمز همه: Test@1404
EMPLOYEES = [
    {"username": "demo_ceo", "name": "غلامرضا مدیرعامل", "role": roles.CEO, "branch": "", "rank": "مدیرعامل"},
    {"username": "demo_coceo", "name": "سینا دستیار مدیرعامل", "role": roles.CO_CEO, "branch": "", "rank": "معاون مدیرعامل"},
    {"username": "demo_bs1", "name": "حامد بی‌طرف", "role": roles.BRANCH_SUPERVISOR, "branch": "branch_1", "rank": "سرپرست شعبه"},
    {"username": "demo_bs2", "name": "مهدی جوادی", "role": roles.BRANCH_SUPERVISOR, "branch": "branch_2", "rank": "سرپرست شعبه"},
    *[
        {
            "username": f"demo_sale{i:02d}",
            "name": f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[i % len(LAST_NAMES)]}",
            "role": roles.SALES_EXPERT,
            "branch": BRANCHES[i % 2],
            "rank": "کارشناس فروش",
        }
        for i in range(1, 11)
    ],
    {"username": "demo_acct1", "name": "پریسا رضایی", "role": roles.ACCOUNTING_FINANCE, "branch": "", "rank": "حسابداری و مالی"},
    {"username": "demo_acct2", "name": "امیر موسوی", "role": roles.ACCOUNTING_FINANCE, "branch": "", "rank": "حسابداری و مالی"},
    {"username": "demo_fact1", "name": "رضا کارخانه", "role": roles.FACTORY_SUPERVISOR, "branch": "", "rank": "سرپرست کارخانه"},
    {"username": "demo_freight1", "name": "کریم باربری", "role": roles.FREIGHT_SUPERVISOR, "branch": "", "rank": "سرپرست باربری"},
]

LOGIN_GUIDE = [
    ("demo_ceo", "مدیرعامل — دسترسی کامل"),
    ("demo_coceo", "دستیار مدیرعامل — گزارش و حسابداری"),
    ("demo_bs1", "سرپرست فروش شعبه کمرد — تایید/اصلاح"),
    ("demo_bs2", "سرپرست فروش شعبه پاسداران — تایید/اصلاح"),
    ("demo_sale01", "کارشناس فروش — ثبت سفارش"),
    ("demo_acct1", "حسابدار ۱ — تایید حسابداری"),
    ("demo_acct2", "حسابدار ۲ — تایید حسابداری"),
    ("demo_fact1", "کارخانه — دریافت و ساخت"),
    ("demo_freight1", "باربری — تحویل‌های امروز"),
]


class Command(BaseCommand):
    help = "Load org-role test users and 300 workflow sales into MySQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-sales",
            action="store_true",
            help="Delete existing sales/customers before loading (keeps users)",
        )

    def handle(self, *args, **options):
        seed_builtin_roles()
        now = timezone.now()
        today = timezone.localdate()

        if options["clear_sales"]:
            self._clear_business_data()

        users_by_role = self._ensure_employees()
        products = self._ensure_products()
        customers = self._ensure_customers()
        sales_created = self._create_sales(users_by_role, customers, products, now, today)

        self.stdout.write(self.style.SUCCESS("\n=== داده تست بارگذاری شد ==="))
        self.stdout.write(f"  کارمندان: {len(EMPLOYEES)}")
        self.stdout.write(f"  مشتریان: {len(customers)}")
        self.stdout.write(f"  سفارش‌ها: {sales_created}")
        self._print_stage_counts()
        self.stdout.write(self.style.WARNING(f"\n  رمز همه حساب‌ها: {PASSWORD}\n"))
        self.stdout.write("  ┌─────────────────┬──────────────────────────────────────┐")
        self.stdout.write("  │ نام کاربری      │ نقش                                  │")
        self.stdout.write("  ├─────────────────┼──────────────────────────────────────┤")
        for username, label in LOGIN_GUIDE:
            self.stdout.write(f"  │ {username:<15} │ {label:<36} │")
        self.stdout.write("  └─────────────────┴──────────────────────────────────────┘")
        self.stdout.write("  کارشناسان فروش: demo_sale01 .. demo_sale10")

    def _print_stage_counts(self):
        from collections import Counter

        counts = Counter(Sale.objects.values_list("workflow_stage", flat=True))
        self.stdout.write("\n  توزیع مراحل:")
        for stage, label in [
            (STAGE_PENDING_BRANCH, "منتظر سرپرست"),
            (STAGE_BRANCH_APPROVED, "منتظر حسابداری"),
            (STAGE_ACCOUNTING_APPROVED, "ارسال کارخانه"),
            (STAGE_IN_PRODUCTION, "در حال ساخت"),
            (STAGE_PRODUCTION_DONE, "آماده باربری"),
            (STAGE_IN_FREIGHT, "در باربری"),
            (STAGE_COMPLETED, "تکمیل"),
        ]:
            self.stdout.write(f"    {label}: {counts.get(stage, 0)}")

        today = timezone.localdate()
        freight_today = Sale.objects.filter(
            delivery_date=today,
            workflow_stage__in={STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT},
        ).count()
        self.stdout.write(f"    تحویل امروز (باربری): {freight_today}")

    def _clear_business_data(self):
        SaleLineItem.objects.all().delete()
        Sale.all_objects.all().delete()
        Customer.all_objects.all().delete()
        self.stdout.write("سفارش‌ها و مشتریان قبلی پاک شد.")

    def _ensure_employees(self):
        users_by_role = {roles.SALES_EXPERT: [], roles.BRANCH_SUPERVISOR: []}
        branch_sup = []
        accounting = []
        factory = []
        freight = []
        ceo_user = None

        for spec in EMPLOYEES:
            user = self._upsert_user(spec)
            role = spec["role"]
            if role == roles.CEO:
                ceo_user = user
            if role == roles.SALES_EXPERT:
                users_by_role[roles.SALES_EXPERT].append(user)
            elif role == roles.BRANCH_SUPERVISOR:
                users_by_role[roles.BRANCH_SUPERVISOR].append(user)
                branch_sup.append(user)
            elif role == roles.ACCOUNTING_FINANCE:
                accounting.append(user)
            elif role == roles.FACTORY_SUPERVISOR:
                factory.append(user)
            elif role == roles.FREIGHT_SUPERVISOR:
                freight.append(user)

            if role in (roles.SALES_EXPERT, roles.BRANCH_SUPERVISOR):
                seller = ensure_seller_for_user(user, branch=spec["branch"] or "branch_1")
                seller.is_active = True
                seller.save()
                StaffAttendance.objects.update_or_create(
                    seller=seller,
                    date=timezone.localdate(),
                    defaults={
                        "status": "present",
                        "approval_status": "approved",
                        "work_branch": spec["branch"] or "branch_1",
                        "check_in_at": timezone.now(),
                    },
                )

        if ceo_user:
            for spec in EMPLOYEES:
                if spec["role"] in (roles.CO_CEO, roles.BRANCH_SUPERVISOR):
                    profile = ensure_staff_profile(User.objects.get(username=spec["username"]))
                    profile.manager = ceo_user
                    profile.save(update_fields=["manager"])

        users_by_role["accounting"] = accounting
        users_by_role["factory"] = factory
        users_by_role["freight"] = freight
        users_by_role["branch_sup"] = branch_sup
        return users_by_role

    def _upsert_user(self, spec):
        username = spec["username"]
        full_name = spec["name"]
        role_slug = spec["role"]
        branch = spec.get("branch") or ""

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@test.local"},
        )
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.is_active = True
        user.is_staff = role_slug in (roles.ADMIN, roles.CEO)
        if created:
            user.set_password(PASSWORD)
        user.save()

        apply_user_access(user, role_slug, branch or None)
        profile = ensure_staff_profile(user, branch or "branch_1")
        profile.job_title = ROLE_LABELS.get(role_slug, role_slug)
        rank_name = spec.get("rank")
        if rank_name:
            org_rank = OrgRank.objects.filter(name=rank_name, is_active=True).first()
            if not org_rank and rank_name in ("مدیرعامل", "معاون مدیرعامل", "سرپرست شعبه", "حسابداری و مالی"):
                org_rank = OrgRank.objects.filter(name__icontains=rank_name[:6], is_active=True).first()
            if org_rank:
                profile.org_rank = org_rank
        profile.save()
        return user

    def _ensure_products(self):
        cat, _ = ProductCategory.objects.get_or_create(
            name="مبلمان تست",
            defaults={"color": "#6366f1", "icon": "🛋️", "sort_order": 0},
        )
        products = []
        for name, sku, fabric, price in PRODUCT_SPECS:
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": cat,
                    "fabric": fabric,
                    "default_price": Decimal(price),
                    "is_active": True,
                },
            )
            product.default_price = Decimal(price)
            product.fabric = fabric
            product.is_active = True
            product.save()
            for color_name, color_hex in [("کرم", "#f5f5dc"), ("طوسی", "#9ca3af")]:
                ProductVariant.objects.get_or_create(
                    product=product,
                    color_name=color_name,
                    defaults={"color_hex": color_hex, "price": Decimal(price), "is_active": True},
                )
            products.append(product)
        return products

    def _ensure_customers(self):
        customers = []
        for i in range(CUSTOMER_COUNT):
            phone = f"0913{(1000000 + i):07d}"[-11:]
            name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i * 3) % len(LAST_NAMES)]}"
            customer, created = Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "full_name": name,
                    "membership_code": generate_membership_code(),
                    "address": f"تهران، خیابان ولیعصر، کوچه {i + 1}، پلاک {(i % 90) + 10}",
                    "wallet_balance": Decimal((i % 5) * 100_000),
                },
            )
            if not created:
                customer.full_name = name
                customer.address = f"تهران، خیابان ولیعصر، کوچه {i + 1}، پلاک {(i % 90) + 10}"
                customer.save(update_fields=["full_name", "address", "updated_at"])
            customers.append(customer)
        return customers

    @transaction.atomic
    def _create_sales(self, users_by_role, customers, products, now, today):
        sales_experts = users_by_role[roles.SALES_EXPERT]
        branch_sup = users_by_role["branch_sup"]
        accounting = users_by_role["accounting"]
        factory = users_by_role["factory"]
        freight = users_by_role["freight"]

        stages = []
        for stage, count in STAGE_WEIGHTS:
            stages.extend([stage] * count)
        random.shuffle(stages)
        stages = stages[:SALE_COUNT]

        created = 0
        for i, stage in enumerate(stages):
            customer = customers[i % len(customers)]
            expert = sales_experts[i % len(sales_experts)]
            branch = BRANCHES[i % 2]
            product = products[i % len(products)]
            variant = product.variants.filter(is_active=True).first()
            qty = (i % 3) + 1
            unit_price = Decimal(product.default_price)
            amount = unit_price * qty
            discount = Decimal((i % 4) * 50_000)
            final_amount = amount - discount
            paid = final_amount if i % 3 == 0 else Decimal(0)
            if paid > 0 and i % 5 == 0:
                paid = final_amount // 2

            sold_at = now - timedelta(days=i % 28, hours=i % 12)
            delivery = today + timedelta(days=1 + (i % 14))
            if stage in {STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT}:
                delivery = today if i % 3 != 0 else today + timedelta(days=1)

            order_status = Sale.ORDER_STATUS_PENDING
            if stage in {
                STAGE_ACCOUNTING_APPROVED,
                STAGE_IN_PRODUCTION,
                STAGE_PRODUCTION_DONE,
                STAGE_IN_FREIGHT,
                STAGE_COMPLETED,
            }:
                order_status = Sale.ORDER_STATUS_CONFIRMED

            bs_user = branch_sup[0] if branch == "branch_1" else branch_sup[1]
            acct_user = accounting[i % len(accounting)]
            fact_user = factory[0] if factory else None
            freight_user = freight[0] if freight else None

            sale = Sale.objects.create(
                customer=customer,
                amount=amount,
                discount_type="amount",
                discount_value=discount,
                discount=discount,
                final_amount=final_amount,
                paid_amount=paid,
                payment_status="paid" if paid >= final_amount else ("installment" if paid > 0 else "unpaid"),
                payment_method=["cash", "card", "check"][i % 3],
                order_kind=Sale.ORDER_KIND_NORMAL,
                order_status=order_status,
                workflow_stage=stage,
                delivery_date=delivery,
                recorded_by=expert,
                branch=branch,
                seller=Seller.objects.filter(user=expert).first(),
                sold_at=sold_at,
                invoice_number=f"DMO-{1404}{i + 1:04d}",
                description=f"سفارش تست {i + 1} — {ROLE_LABELS.get(roles.SALES_EXPERT, 'فروش')}",
            )

            if stage != STAGE_PENDING_BRANCH:
                sale.branch_approved_at = sold_at + timedelta(hours=2)
                sale.branch_approved_by = bs_user
            if stage in {
                STAGE_ACCOUNTING_APPROVED,
                STAGE_IN_PRODUCTION,
                STAGE_PRODUCTION_DONE,
                STAGE_IN_FREIGHT,
                STAGE_COMPLETED,
            }:
                sale.accounting_approved_at = sold_at + timedelta(hours=6)
                sale.accounting_approved_by = acct_user
            if stage in {STAGE_IN_PRODUCTION, STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT, STAGE_COMPLETED}:
                if fact_user:
                    sale.factory_received_at = sold_at + timedelta(hours=12)
                    sale.factory_received_by = fact_user
            if stage in {STAGE_PRODUCTION_DONE, STAGE_IN_FREIGHT, STAGE_COMPLETED}:
                sale.production_done_at = sold_at + timedelta(days=2)
            if stage in {STAGE_IN_FREIGHT, STAGE_COMPLETED}:
                if freight_user:
                    sale.freight_received_at = sold_at + timedelta(days=3)
                    sale.freight_received_by = freight_user
            if stage == STAGE_COMPLETED:
                sale.freight_completed_at = sold_at + timedelta(days=4)

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
                unit_price=unit_price,
                line_total=amount,
            )
            created += 1

        return created
