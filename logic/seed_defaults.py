"""Seed اولیه سیستم — طرح حساب، سطوح وفاداری، متریال نمونه."""

from decimal import Decimal

from backend.models import LoyaltyLevel, Material, ProductMaterial
from logic.accounting_accounts import seed_accounts
from logic.config_seed import seed_config_defaults, _table_exists

DEFAULT_LOYALTY_LEVELS = [
    {"name": "برنز", "min_purchase": 0, "max_purchase": 10_000_000, "color": "#cd7f32"},
    {"name": "نقره‌ای", "min_purchase": 10_000_000, "max_purchase": 30_000_000, "color": "#94a3b8"},
    {"name": "طلایی", "min_purchase": 30_000_000, "max_purchase": 70_000_000, "color": "#f59e0b"},
    {"name": "VIP", "min_purchase": 70_000_000, "max_purchase": None, "color": "#8b5cf6"},
]

DEMO_MATERIALS = [
    {
        "name": "پارچه مخمل",
        "color_name": "کرم",
        "color_hex": "#f5f5dc",
        "sku": "MAT-VEL-01",
        "unit": "متر",
        "unit_cost": 850_000,
        "stock": 120,
        "description": "مخمل ترک — نمونه seed",
    },
    {
        "name": "چرم مصنوعی",
        "color_name": "قهوه‌ای",
        "color_hex": "#8b4513",
        "sku": "MAT-LTH-02",
        "unit": "متر",
        "unit_cost": 620_000,
        "stock": 85,
        "description": "چرم صندلی — نمونه seed",
    },
    {
        "name": "اسفنج ۳۵",
        "color_name": "",
        "color_hex": "#e5e7eb",
        "sku": "MAT-SPF-03",
        "unit": "متر",
        "unit_cost": 180_000,
        "stock": 200,
        "description": "اسفنج نرم — نمونه seed",
    },
    {
        "name": "MDF ۱۶میل",
        "color_name": "",
        "color_hex": "#d4a574",
        "sku": "MAT-MDF-04",
        "unit": "ورق",
        "unit_cost": 1_200_000,
        "stock": 45,
        "description": "MDF سفید — نمونه seed",
    },
]


def seed_accounts_safe():
    """طرح حساب — فقط اگر جدول حساب وجود دارد."""
    from backend.models import Account

    if not _table_exists(Account):
        return
    from logic.accounting_accounts import seed_accounts

    seed_accounts()


def seed_loyalty_levels():
    """سطوح باشگاه مشتریان — idempotent."""
    from backend.models import LoyaltyLevel

    if not _table_exists(LoyaltyLevel):
        return
    for spec in DEFAULT_LOYALTY_LEVELS:
        LoyaltyLevel.objects.update_or_create(
            name=spec["name"],
            defaults={
                "min_purchase": Decimal(spec["min_purchase"]),
                "max_purchase": Decimal(spec["max_purchase"]) if spec["max_purchase"] is not None else None,
                "color": spec.get("color", "#6366f1"),
                "is_active": True,
            },
        )


def seed_system_defaults():
    """تنظیمات پایه: شعب، lookup، منو، نقش‌ها، طرح حساب، سطوح وفاداری."""
    seed_config_defaults()
    seed_accounts_safe()
    seed_loyalty_levels()


def seed_demo_materials(*, user=None, link_products=True):
    """متریال نمونه — با ثبت حسابداری موجودی (ریال)."""
    from logic.materials import create_material

    created = []
    for spec in DEMO_MATERIALS:
        material = Material.objects.filter(sku=spec["sku"]).first()
        if material:
            created.append(material)
            continue
        material = create_material(spec, user=user, auto_approve=True)
        created.append(material)

    if link_products:
        _link_demo_materials_to_products(created)
    return created


def _link_demo_materials_to_products(materials):
    """اتصال متریال نمونه به محصولات موجود (در صورت وجود)."""
    from backend.models import Product

    if not materials:
        return
    products = list(Product.objects.filter(is_active=True, is_deleted=False).order_by("id")[:5])
    if not products:
        return
    qty_cycle = [Decimal("2.5"), Decimal("1"), Decimal("4"), Decimal("0.5")]
    for index, product in enumerate(products):
        material = materials[index % len(materials)]
        ProductMaterial.objects.get_or_create(
            product=product,
            material=material,
            defaults={
                "quantity": qty_cycle[index % len(qty_cycle)],
                "sort_order": index,
            },
        )
