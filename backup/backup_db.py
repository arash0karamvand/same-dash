"""اسکریپت بکاپ دیتابیس و خروجی‌گیری از اطلاعات.

این اسکریپت دو خروجی می‌سازد و در فولدر backup/exports ذخیره می‌کند:
    ۱) کپی فایل خام دیتابیس SQLite (db.sqlite3)
    ۲) خروجی JSON کامل داده‌ها با استفاده از دستور dumpdata خود Django

اجرا (از ریشه پروژه):
    py backup/backup_db.py

هیچ پکیج خارجی لازم نیست؛ فقط از کتابخانه استاندارد و ابزار خود Django
استفاده می‌شود.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ریشه پروژه (یک پوشه بالاتر از این فایل)
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "backup" / "exports"


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_sqlite_file(stamp):
    """کپی مستقیم فایل دیتابیس SQLite در صورت وجود."""
    db_path = BASE_DIR / "db.sqlite3"
    if not db_path.exists():
        print("هشدار: فایل db.sqlite3 یافت نشد؛ از کپی خام صرف‌نظر شد.")
        return None
    target = EXPORT_DIR / f"db_backup_{stamp}.sqlite3"
    shutil.copy2(db_path, target)
    print(f"کپی دیتابیس ساخته شد: {target}")
    return target


def dump_json(stamp):
    """خروجی JSON کامل داده‌ها با dumpdata خود Django."""
    target = EXPORT_DIR / f"data_dump_{stamp}.json"
    manage_py = BASE_DIR / "manage.py"
    with open(target, "w", encoding="utf-8") as out:
        # از همان مفسر پایتون فعلی استفاده می‌کنیم تا نیاز به تنظیم PATH نباشد.
        result = subprocess.run(
            [sys.executable, str(manage_py), "dumpdata", "--indent", "2",
             "--exclude", "contenttypes", "--exclude", "auth.permission"],
            stdout=out,
            stderr=subprocess.PIPE,
            text=True,
        )
    if result.returncode == 0:
        print(f"خروجی JSON داده‌ها ساخته شد: {target}")
        return target
    print("خطا در ساخت خروجی JSON:")
    print(result.stderr)
    return None


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    stamp = timestamp()
    print(f"شروع بکاپ در {stamp} ...")
    backup_sqlite_file(stamp)
    dump_json(stamp)
    print("بکاپ به پایان رسید.")


if __name__ == "__main__":
    main()
