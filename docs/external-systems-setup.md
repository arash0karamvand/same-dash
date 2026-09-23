# راهنمای تنظیم سیستم‌های خارجی (Odoo و ERPNext)

این سند راهنمای تنظیم اتصال به سیستم‌های حسابداری خارجی است.

## 📋 فهرست مطالب

- [نمای کلی](#نمای-کلی)
- [تنظیم Odoo](#تنظیم-odoo)
- [تنظیم ERPNext](#تنظیم-erpnext)
- [عیب‌یابی](#عیب‌یابی)

---

## نمای کلی

صفحه **صورت‌های مالی** در بخش حسابداری قابلیت ارسال خودکار اسناد حسابداری به سیستم‌های خارجی را دارد:

- **Odoo**: ارسال به‌صورت `account.move`
- **ERPNext**: ارسال به‌صورت `Journal Entry`
- **Beancount**: خروجی فایل متنی

این اتصالات **اختیاری** هستند. اگر تنظیم نشوند، سایر قسمت‌های سیستم کاملاً کار می‌کنند.

---

## تنظیم Odoo

### پیش‌نیازها

1. یک نمونه Odoo نصب شده با ماژول حسابداری
2. یک کاربر با دسترسی API
3. دسترسی شبکه به سرور Odoo

### متغیرهای محیطی

در فایل `.env` یا محیط سرور خود، متغیرهای زیر را تنظیم کنید:

```bash
# آدرس سرور Odoo (بدون / در انتها)
ODOO_URL=https://your-odoo-server.com

# نام پایگاه داده Odoo
ODOO_DB=your_database_name

# نام کاربری
ODOO_USER=admin

# رمز عبور
ODOO_PASSWORD=your_secure_password

# (اختیاری) شناسه دفتر روزنامه پیش‌فرض
ODOO_JOURNAL_ID=1
```

### تست اتصال

بعد از تنظیم متغیرها:

1. سرور Django را restart کنید:
   ```bash
   python manage.py runserver
   ```

2. به صفحه **حسابداری > صورت‌های مالی** بروید

3. در بخش "موتورها و اتصال‌های خارجی"، باید Odoo به‌عنوان **✓ فعال** نشان داده شود

4. دکمه **ارسال به Odoo** باید فعال (غیرخاکستری) باشد

### نمونه ارسال

وقتی روی **ارسال به Odoo** کلیک کنید:

```python
# هر سند حسابداری به این شکل ارسال می‌شود:
{
    "move_type": "entry",
    "date": "2026-09-22",
    "ref": "ACC-001",
    "line_ids": [
        (0, 0, {
            "account_id": 123,
            "name": "شرح تراکنش",
            "debit": 1000000,
            "credit": 0
        }),
        (0, 0, {
            "account_id": 456,
            "name": "شرح تراکنش",
            "debit": 0,
            "credit": 1000000
        })
    ]
}
```

---

## تنظیم ERPNext

### پیش‌نیازها

1. یک نمونه ERPNext نصب شده
2. API Key و API Secret ایجاد شده
3. یک شرکت (Company) ایجاد شده در ERPNext

### ایجاد API Credentials

1. به ERPNext خود وارد شوید
2. به **User** > **API Keys** بروید
3. روی **Generate Keys** کلیک کنید
4. `API Key` و `API Secret` را کپی کنید

### متغیرهای محیطی

```bash
# آدرس سرور ERPNext (بدون / در انتها)
ERPNEXT_URL=https://your-erpnext-server.com

# API Key
ERPNEXT_API_KEY=your_api_key_here

# API Secret
ERPNEXT_API_SECRET=your_api_secret_here

# (اختیاری) نام شرکت
ERPNEXT_COMPANY=شرکت نمونه

# (اختیاری) مخفف شرکت
ERPNEXT_COMPANY_ABBR=CO
```

### تست اتصال

مشابه Odoo:

1. سرور را restart کنید
2. به صفحه صورت‌های مالی بروید
3. ERPNext باید **✓ فعال** باشد
4. دکمه **ارسال به ERPNext** فعال می‌شود

### نمونه ارسال

```json
{
    "doctype": "Journal Entry",
    "voucher_type": "Journal Entry",
    "company": "شرکت نمونه",
    "posting_date": "2026-09-22",
    "user_remark": "شرح سند",
    "cheque_no": "ACC-001",
    "accounts": [
        {
            "account": "1101 - CO",
            "account_code": "1101",
            "debit_in_account_currency": 1000000,
            "credit_in_account_currency": 0
        },
        {
            "account": "2101 - CO",
            "account_code": "2101",
            "debit_in_account_currency": 0,
            "credit_in_account_currency": 1000000
        }
    ]
}
```

---

## عیب‌یابی

### دکمه‌ها غیرفعال هستند

**علت**: متغیرهای محیطی تنظیم نشده‌اند

**راه‌حل**:
1. فایل `.env` را بررسی کنید
2. مطمئن شوید همه متغیرهای لازم موجود هستند
3. سرور را restart کنید

### خطای Authentication

**Odoo**:
```
ورود به Odoo ناموفق بود.
```

**راه‌حل**:
- نام کاربری و رمز عبور را بررسی کنید
- مطمئن شوید کاربر دسترسی XML-RPC دارد

**ERPNext**:
```
ERPNext سند را نپذیرفت
```

**راه‌حل**:
- API Key و Secret را بررسی کنید
- مطمئن شوید API Keys منقضی نشده‌اند

### حساب‌ها یافت نمی‌شوند

**خطا**:
```
حساب 1101 در Odoo/ERPNext پیدا نشد.
```

**راه‌حل**:
1. مطمئن شوید Chart of Accounts در سیستم هدف ایجاد شده
2. کدهای حساب در هر دو سیستم یکسان باشند
3. برای ERPNext، فرمت `{code} - {abbr}` استفاده شود (مثلاً `1101 - CO`)

### مشکلات شبکه

**خطا**:
```
Connection timeout
```

**راه‌حل**:
- آدرس URL را بررسی کنید
- فایروال و تنظیمات شبکه را چک کنید
- مطمئن شوید سرور هدف در دسترس است

---

## توجه مهم

⚠️ **امنیت**: 
- API Keys و Passwords را هرگز در git commit نکنید
- از فایل `.env` استفاده کنید و آن را به `.gitignore` اضافه کنید
- در production از HTTPS استفاده کنید

✅ **بهترین روش‌ها**:
- قبل از ارسال دسته‌جمعی، با یک سند تست کنید
- backup منظم از هر دو سیستم بگیرید
- log های سرور را برای debugging نگه دارید

---

## پشتیبانی

برای مشکلات بیشتر:
1. لاگ‌های Django را بررسی کنید: `python manage.py runserver`
2. لاگ‌های Odoo/ERPNext را بررسی کنید
3. از بخش Developer Tools مرورگر Console را چک کنید

---

📅 آخرین به‌روزرسانی: ۲۲ شهریور ۱۴۰۵
