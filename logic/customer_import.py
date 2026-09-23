"""Import مشتریان و داده‌های CRM از فایل‌های اکسل"""

import logging
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.db import transaction

from backend.models import Customer, LoyaltyLevel

logger = logging.getLogger(__name__)


def parse_customer_excel(file_path):
    """
    خواندن فایل اکسل مشتریان
    
    فرمت فایل:
    - ردیف اول: هدرها
    - ستون‌ها: نام، تلفن، آدرس، کد عضویت، خریدهای کل، تولد، ایمیل، توضیحات
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    customers = []
    header_row = None
    
    # پیدا کردن ردیف هدر
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
        if any(cell for cell in row if cell):
            # اگر نام یا تلفن در هدر پیدا شد
            if any(str(cell or "").strip() in ["نام", "تلفن", "موبایل"] for cell in row):
                header_row = i
                break
    
    if not header_row:
        header_row = 1
    
    # خواندن داده‌ها
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        # رد کردن ردیف‌های خالی
        if not row or not any(cell for cell in row):
            continue
        
        # نام (معمولاً ستون اول یا دوم)
        full_name = None
        for cell in row[:3]:
            if cell and isinstance(cell, str) and len(cell.strip()) > 2:
                full_name = cell.strip()
                break
        
        if not full_name:
            continue
        
        # تلفن (جستجوی عدد 11 رقمی)
        phone = None
        for cell in row:
            if cell:
                phone_str = str(cell).strip().replace("-", "").replace(" ", "")
                if phone_str.isdigit() and 10 <= len(phone_str) <= 12:
                    phone = phone_str[-11:]  # آخرین 11 رقم
                    break
        
        if not phone:
            logger.warning(f"تلفن یافت نشد برای: {full_name}")
            continue
        
        # تلاش برای پیدا کردن سایر اطلاعات
        address = ""
        membership_code = ""
        total_purchase = 0
        birthday = None
        email = ""
        notes = ""
        
        # آدرس (معمولاً طولانی‌ترین رشته)
        for cell in row:
            if cell and isinstance(cell, str) and len(cell) > 20 and not "@" in cell:
                address = cell.strip()
                break
        
        # ایمیل
        for cell in row:
            if cell and isinstance(cell, str) and "@" in cell:
                email = cell.strip()
                break
        
        # مبلغ خرید (جستجوی عدد بزرگ)
        for cell in row:
            if cell and isinstance(cell, (int, float)) and cell > 10000:
                total_purchase = Decimal(str(cell))
                break
        
        customers.append({
            "full_name": full_name,
            "phone": phone,
            "address": address,
            "membership_code": membership_code,
            "total_purchase": total_purchase,
            "birthday": birthday,
            "email": email,
            "notes": notes,
        })
    
    wb.close()
    return customers


def smart_detect_columns(ws):
    """تشخیص هوشمند ستون‌ها بر اساس محتوا"""
    headers = []
    first_row = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
    
    for i, cell in enumerate(first_row):
        header = str(cell or "").strip().lower()
        if "نام" in header or "name" in header:
            headers.append(("name", i))
        elif "تلفن" in header or "موبایل" in header or "phone" in header:
            headers.append(("phone", i))
        elif "آدرس" in header or "address" in header:
            headers.append(("address", i))
        elif "عضویت" in header or "membership" in header:
            headers.append(("membership", i))
        elif "خرید" in header or "purchase" in header:
            headers.append(("purchase", i))
        elif "تولد" in header or "birthday" in header:
            headers.append(("birthday", i))
        elif "ایمیل" in header or "email" in header:
            headers.append(("email", i))
    
    return dict(headers)


@transaction.atomic
def import_customers_from_excel(file_path, user):
    """
    وارد کردن مشتریان از اکسل به دیتابیس
    
    Returns:
        dict: آمار import شامل تعداد ساخته‌شده، به‌روز‌شده و خطاها
    """
    logger.info(f"شروع import مشتریان از {file_path}")
    
    data = parse_customer_excel(file_path)
    created = []
    updated = []
    errors = []
    
    for item in data:
        try:
            phone = item["phone"]
            
            # جستجوی مشتری موجود
            customer, is_new = Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "full_name": item["full_name"],
                    "address": item["address"],
                    "membership_code": item["membership_code"] or None,
                    "email": item["email"],
                    "birthday": item["birthday"],
                    "notes": item["notes"],
                }
            )
            
            if not is_new:
                # به‌روزرسانی اطلاعات موجود
                customer.full_name = item["full_name"]
                if item["address"]:
                    customer.address = item["address"]
                if item["email"]:
                    customer.email = item["email"]
                if item["notes"]:
                    customer.notes = item["notes"]
                customer.save()
                updated.append(customer)
            else:
                created.append(customer)
            
            # تعیین سطح loyalty بر اساس خریدهای کل
            if item["total_purchase"] > 0:
                assign_loyalty_level(customer, item["total_purchase"])
            
        except Exception as e:
            logger.error(f"خطا در import مشتری {item.get('full_name')}: {e}")
            errors.append({
                "name": item.get("full_name"),
                "phone": item.get("phone"),
                "error": str(e)
            })
    
    # ثبت لاگ
    from logic.audit import log_action
    log_action(
        user,
        "import",
        f"وارد کردن {len(created)} مشتری جدید، {len(updated)} به‌روزرسانی از فایل اکسل",
        "Customer",
    )
    
    result = {
        "created": len(created),
        "updated": len(updated),
        "errors": len(errors),
        "error_details": errors[:10],  # فقط 10 خطای اول
        "total": len(data),
    }
    
    logger.info(f"import تکمیل شد: {result}")
    return result


def assign_loyalty_level(customer, total_purchase):
    """تعیین سطح loyalty بر اساس مبلغ خریدهای کل"""
    level = LoyaltyLevel.objects.filter(
        is_active=True,
        min_purchase__lte=total_purchase
    ).filter(
        models.Q(max_purchase__gte=total_purchase) | models.Q(max_purchase__isnull=True)
    ).order_by("-min_purchase").first()
    
    if level:
        customer.level = level
        customer.save(update_fields=["level"])


def export_customers_to_excel(queryset, filename="customers.xlsx"):
    """خروجی اکسل از لیست مشتریان"""
    from logic.excel_export import FormattedExcelExporter
    
    exp = FormattedExcelExporter("مشتریان")
    exp.add_header("لیست مشتریان")
    
    # هدر جدول
    headers = [
        "ردیف",
        "نام و نام خانوادگی",
        "تلفن",
        "کد عضویت",
        "سطح باشگاه",
        "آدرس",
        "تاریخ عضویت",
        "آخرین خرید",
    ]
    exp.add_table_header(headers)
    
    # داده‌ها
    for idx, customer in enumerate(queryset, 1):
        exp.add_table_row([
            idx,
            customer.full_name,
            customer.phone,
            customer.membership_code or "—",
            customer.level.name if customer.level else "—",
            customer.address[:50] if customer.address else "—",
            customer.joined_at.strftime("%Y/%m/%d"),
            customer.last_purchase_at.strftime("%Y/%m/%d") if customer.last_purchase_at else "—",
        ])
    
    return exp.save_response(filename)


def import_from_uploaded_file(uploaded_file, user):
    """
    Import از فایل آپلود شده در Django
    
    Args:
        uploaded_file: InMemoryUploadedFile یا TemporaryUploadedFile
        user: کاربر درخواست‌کننده
    
    Returns:
        dict: نتیجه import
    """
    import tempfile
    
    # ذخیره موقت
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    
    try:
        result = import_customers_from_excel(tmp_path, user)
    finally:
        # حذف فایل موقت
        Path(tmp_path).unlink(missing_ok=True)
    
    return result


# برای استفاده در management commands
def bulk_import_directory(directory_path, user):
    """Import تمام فایل‌های اکسل در یک دایرکتوری"""
    directory = Path(directory_path)
    results = []
    
    for file_path in directory.glob("*.xlsx"):
        if file_path.name.startswith("~"):  # فایل‌های موقت
            continue
        
        logger.info(f"Processing {file_path.name}...")
        try:
            result = import_customers_from_excel(str(file_path), user)
            results.append({
                "file": file_path.name,
                **result
            })
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            results.append({
                "file": file_path.name,
                "error": str(e)
            })
    
    return results
