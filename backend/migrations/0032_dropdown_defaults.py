from django.db import migrations


# عنوان دسته فقط همین‌جا نوشته می‌شود تا داخل برنامهٔ در حال اجرا نماند.
CATEGORY_LABELS = {
    "payment_method": "روش پرداخت",
    "payment_status": "وضعیت پرداخت",
    "order_kind": "نوع سفارش",
    "order_status": "وضعیت سفارش",
    "discount_type": "نوع تخفیف",
    "accounting_mode": "حالت حسابداری",
    "workflow_stage": "مرحله گردش سفارش",
    "fulfillment_route": "مسیر تحویل",
    "receive_kind": "نوع دریافت کارخانه",
    "attendance_status": "وضعیت حضور",
    "approval_status": "وضعیت تایید",
    "staff_kind": "نوع پرسنل",
    "material_unit": "واحد متریال",
    "document_code": "کد نوع سند",
    "account_class": "گروه حساب",
    "normal_balance": "ماهیت حساب",
    "source_module": "ماژول مبدأ حسابداری",
    "frame_design_style": "سبک طراحی کلاف",
    "frame_wood_type": "جنس چوب",
    "frame_piece_kind": "نوع قطعه مبل",
    "frame_arm_style": "حالت دسته",
    "frame_component_type": "نوع قطعه سرویس",
    "frame_rule_key": "قانون متریال کلاف",
    "workshop_recipe_kind": "نوع دستور کارگاه",
    "workshop_paint_category": "دسته رنگ",
    "workshop_fabric_category": "دسته پارچه",
    "workshop_fabric_company": "شرکت پارچه",
    "workshop_fabric_country": "کشور پارچه",
    "beta_workshop_kind": "نوع واحد نجاری",
    "beta_carpentry_kind": "نوع دستور نجاری",
    "beta_carpentry_status": "وضعیت دستور نجاری",
    "beta_paint_kind": "نوع سفارش رنگ",
    "beta_paint_stage": "مراحل خط رنگ",
    "beta_upholstery_stage": "مراحل رویه‌کوبی",
    "beta_qc_status": "وضعیت کنترل کیفیت",
    "beta_qc_grade": "گریدهای کنترل کیفیت",
    "merchant_service_flow": "جهت سرویس بازرگان",
    "carpentry_tool_status": "وضعیت ابزار نجاری",
    "material_usage_kind": "نوع مصرف متریال",
    "material_valuation_method": "روش ارزیابی",
    "material_freight_treatment": "نحوه ثبت حمل",
}

# (category, code, label, sort_order)
DEFAULT_ROWS = [
    ("merchant_service_flow", "give", "سرویس را به بازرگان می‌دهیم تا بسازد", 0),
    ("merchant_service_flow", "receive", "بازرگان سرویس را به ما می‌دهد تا بسازیم", 1),
    ("merchant_service_flow", "both", "هر دو طرف", 2),
    ("carpentry_tool_status", "active", "فعال", 0),
    ("carpentry_tool_status", "maintenance", "در تعمیر", 1),
    ("carpentry_tool_status", "retired", "اسقاط", 2),
    ("material_usage_kind", "wood", "چوب", 0),
    ("material_usage_kind", "paint", "رنگ", 1),
    ("material_usage_kind", "fabric", "پارچه", 2),
    ("material_usage_kind", "foam", "اسفنج", 3),
    ("material_usage_kind", "webbing", "تسمه", 4),
    ("material_usage_kind", "cushion", "کوسن", 5),
    ("material_usage_kind", "other", "سایر", 6),
    ("material_valuation_method", "weighted_average", "میانگین موزون", 0),
    ("material_valuation_method", "fifo", "FIFO", 1),
    ("material_freight_treatment", "capitalize", "سرشکن در بهای کالا", 0),
    ("material_freight_treatment", "period_expense", "هزینه دوره", 1),
]


def insert_dropdown_defaults(apps, schema_editor):
    LookupOption = apps.get_model("backend", "LookupOption")
    for category, code, label, sort_order in DEFAULT_ROWS:
        meta = {"category_label": CATEGORY_LABELS[category]}
        row, created = LookupOption.objects.get_or_create(
            category=category,
            code=code,
            defaults={
                "label": label,
                "sort_order": sort_order,
                "is_active": True,
                "meta": meta,
            },
        )
        if not created:
            stored = dict(row.meta or {})
            stored.setdefault("category_label", meta["category_label"])
            row.meta = stored
            row.save(update_fields=["meta"])

    for category, title in CATEGORY_LABELS.items():
        for row in LookupOption.objects.filter(category=category):
            stored = dict(row.meta or {})
            if stored.get("category_label") == title:
                continue
            stored["category_label"] = title
            row.meta = stored
            row.save(update_fields=["meta"])


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0031_merchant_workshop"),
    ]

    operations = [
        migrations.RunPython(insert_dropdown_defaults, migrations.RunPython.noop),
    ]
