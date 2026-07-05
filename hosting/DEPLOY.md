# راهنمای استقرار (Deploy)

راهنمای اجرای پروژه روی سرور/هاست.

## پیش‌نیازها

- Python 3.14+ و Django (از قبل نصب‌شده)
- Node.js 20+ برای build فرانت‌اند
- یک وب‌سرور (Nginx) و WSGI server (Gunicorn/Waitress)

## گام‌ها

### ۱) تنظیم متغیرهای محیطی

```bash
cp hosting/.env.sample .env
# مقادیر واقعی را در .env قرار دهید
```

مهم‌ترین مقادیر تولید:

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY` مقدار تصادفی و محرمانه
- `DJANGO_ALLOWED_HOSTS` دامنه واقعی

> نکته: `backend/settings.py` مقادیر حساس (`DJANGO_SECRET_KEY`، `DJANGO_DEBUG`،
> `DJANGO_ALLOWED_HOSTS`، اعتبارنامه پیامک) را از متغیرهای محیطی می‌خواند. در
> تولید حتماً `DJANGO_DEBUG=False` و `DJANGO_SECRET_KEY` را تنظیم کنید؛ اگر
> `DEBUG=False` باشد و `SECRET_KEY` تنظیم نشده باشد، اجرا با خطا متوقف می‌شود
> (به‌عمد، تا secret ناامن استفاده نشود).

### ۲) آماده‌سازی بک‌اند

```bash
pip install -r requirements.txt
```

**MySQL / MariaDB:** قبل از migrate یک دیتابیس با charset مناسب فارسی بسازید:

```sql
CREATE DATABASE same_dashboard
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

> **نسخه:** Django 6 به **MySQL 8+** یا **MariaDB 10.6+** نیاز دارد.  
> اگر XAMPP با MariaDB 10.4 دارید، MariaDB/MySQL را ارتقا دهید یا موقت `DB_ENGINE=sqlite` بگذارید.

فایل `.env` را از `.env.example` کپی کرده و `DB_USER` / `DB_PASSWORD` را تنظیم کنید.

**انتقال از SQLite (اختیاری):**

```bash
# با DB_ENGINE=sqlite
py manage.py dumpdata --indent 2 --exclude contenttypes --exclude auth.permission -o backup/exports/migrate_to_mysql.json

# سپس .env را به MySQL تغییر دهید و:
py manage.py migrate
py manage.py loaddata backup/exports/migrate_to_mysql.json
```

```bash
py manage.py migrate
py manage.py collectstatic --noinput
py manage.py createsuperuser   # ساخت کاربر مدیر (فقط از این طریق، نه داخل کد)
```

> کاربر مدیر تنها با دستور `createsuperuser` ساخته می‌شود. هیچ کاربر/رمز پیش‌فرضی
> در کد وجود ندارد. کاربرانی که از طریق ثبت‌نام عمومی ساخته می‌شوند نقش `pending`
> دارند و تا تخصیص نقش توسط مدیر، دسترسی داده‌ای ندارند.

### ۳) build فرانت‌اند

```bash
cd ui
npm install
npm run build
```

خروجی در `ui/dist/` تولید می‌شود که توسط وب‌سرور سرو می‌شود.

### ۴) اجرای بک‌اند با WSGI

نمونه با Gunicorn (لینوکس):

```bash
gunicorn backend.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

روی ویندوز می‌توانید از `waitress` استفاده کنید:

```bash
waitress-serve --port=8000 backend.wsgi:application
```

### ۵) پیکربندی Nginx (نمونه)

```nginx
server {
    listen 80;
    server_name example.com;

    location /api/  { proxy_pass http://127.0.0.1:8000; }
    location /auth/ { proxy_pass http://127.0.0.1:8000; }
    location /admin/ { proxy_pass http://127.0.0.1:8000; }
    location /static/ { alias /path/to/project/staticfiles/; }

    location / {
        root /path/to/project/ui/dist;
        try_files $uri /index.html;
    }
}
```

## بکاپ

قبل از هر استقرار مهم، از دیتابیس بکاپ بگیرید:

```bash
py backup/backup_db.py
```
