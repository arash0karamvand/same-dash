"""نمونه پیکربندی Gunicorn برای اجرای بک‌اند در محیط تولید (لینوکس).

اجرا:
    gunicorn backend.wsgi:application -c hosting/gunicorn_config.py
"""

import multiprocessing

# آدرس و پورت اتصال (پشت Nginx)
bind = "127.0.0.1:8000"

# تعداد workerها بر اساس تعداد هسته‌های CPU
workers = multiprocessing.cpu_count() * 2 + 1

# سقف زمان پردازش هر درخواست (ثانیه)
timeout = 60

# ثبت لاگ روی خروجی استاندارد تا توسط systemd/داکر جمع‌آوری شود
accesslog = "-"
errorlog = "-"
loglevel = "info"
