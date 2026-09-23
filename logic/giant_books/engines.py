"""وضعیت کتابخانه‌هایی که موتور دفاتر به آن‌ها تکیه می‌کند."""

import importlib


def _imports(module_name):
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def engine_status(*, odoo_ready=False, erpnext_ready=False, beancount_engine="builtin"):
    return [
        {
            "id": "py-moneyed",
            "label": "py-moneyed",
            "active": _imports("moneyed"),
            "detail": "مبالغ ریال با ارز IRR محاسبه می‌شود.",
        },
        {
            "id": "pandas",
            "label": "Pandas",
            "active": _imports("pandas"),
            "detail": "گردش حساب‌ها و صورت‌ها با DataFrame جمع می‌شود.",
        },
        {
            "id": "beancount",
            "label": "Beancount",
            "active": True,
            "detail": (
                "دفتر متنی ساخته و با کتابخانهٔ Beancount خوانده می‌شود."
                if beancount_engine == "beancount"
                else "دفتر متنی ساخته می‌شود. کتابخانهٔ Beancount روی این ماشین نصب نیست و تراز هر سند داخل خود موتور چک می‌شود."
            ),
        },
        {
            "id": "django-hordak",
            "label": "Django-Hordak",
            "active": True,
            "detail": (
                "جمع پاهای علامت‌دار هر سند با py-moneyed صفر می‌شود. "
                "خود بسته نصب نمی‌شود چون openpyxl را به نسخهٔ ۲ قفل می‌کند و یک کدینگ جدا می‌سازد."
            ),
        },
        {
            "id": "django-ledger",
            "label": "Django-Ledger",
            "active": True,
            "detail": "ترازنامه، صورت سود و زیان و جریان وجوه نقد روی همین اسناد ساخته می‌شود. اپ جداگانهٔ دفتر دوم سوار نشده است.",
        },
        {
            "id": "odoo",
            "label": "Odoo",
            "active": odoo_ready,
            "detail": (
                "سند account.move از طریق XML-RPC ارسال می‌شود."
                if odoo_ready
                else "پیش‌نویس account.move آماده است. با ODOO_URL و ODOO_DB و ODOO_USER و ODOO_PASSWORD ارسال می‌شود."
            ),
        },
        {
            "id": "erpnext",
            "label": "ERPNext",
            "active": erpnext_ready,
            "detail": (
                "Journal Entry از طریق REST ارسال می‌شود."
                if erpnext_ready
                else "Journal Entry آماده است. با ERPNEXT_URL و ERPNEXT_API_KEY و ERPNEXT_API_SECRET ارسال می‌شود."
            ),
        },
    ]
