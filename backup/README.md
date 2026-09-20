# بکاپ دیتابیس

اسکریپت‌های تهیه نسخه پشتیبان و خروجی‌گیری از اطلاعات MySQL.

## اجرا

از ریشه پروژه:

```bash
py backup/backup_db.py
```

## خروجی‌ها

فایل‌ها در پوشه `backup/exports/` ساخته می‌شوند:

- `db_backup_<timestamp>.sql` — دامپ خام MySQL (اگر `mysqldump` نصب باشد)
- `data_dump_<timestamp>.json` — خروجی JSON کامل داده‌ها (با `dumpdata`)

## بازگردانی (Restore)

برای بازگردانی از خروجی JSON:

```bash
py manage.py loaddata backup/exports/data_dump_<timestamp>.json
```

برای بازگردانی دامپ خام MySQL:

```bash
mysql --default-character-set=utf8mb4 -u USER -p DB_NAME < backup/exports/db_backup_<timestamp>.sql
```

> نکته: پوشه `exports/` نباید در version control قرار گیرد (در `.gitignore` پروژه اضافه شود).
