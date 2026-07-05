# بکاپ دیتابیس

اسکریپت‌های تهیه نسخه پشتیبان و خروجی‌گیری از اطلاعات.

## اجرا

از ریشه پروژه:

```bash
py backup/backup_db.py
```

## خروجی‌ها

فایل‌ها در پوشه `backup/exports/` ساخته می‌شوند:

- `db_backup_<timestamp>.sqlite3` — کپی خام فایل دیتابیس SQLite
- `data_dump_<timestamp>.json` — خروجی JSON کامل داده‌ها (با `dumpdata`)

## بازگردانی (Restore)

برای بازگردانی از خروجی JSON:

```bash
py manage.py loaddata backup/exports/data_dump_<timestamp>.json
```

یا برای بازگردانی فایل خام، کافی است فایل sqlite را جایگزین `db.sqlite3` در ریشه کنید.

> نکته: پوشه `exports/` نباید در version control قرار گیرد (در `.gitignore` پروژه اضافه شود).
