"""اسکریپت بکاپ دیتابیس و خروجی‌گیری از اطلاعات.

این اسکریپت دو خروجی می‌سازد و در فولدر backup/exports ذخیره می‌کند:
    ۱) دامپ خام MySQL (mysqldump) در صورت نصب بودن کلاینت
    ۲) خروجی JSON کامل داده‌ها با استفاده از دستور dumpdata خود Django

اجرا (از ریشه پروژه):
    py backup/backup_db.py
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ریشه پروژه (یک پوشه بالاتر از این فایل)
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "backup" / "exports"


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_env():
    sys.path.insert(0, str(BASE_DIR))
    from backend.db import load_env_file

    load_env_file(BASE_DIR)


def backup_mysql_dump(stamp):
    """خروجی SQL خام با mysqldump."""
    _load_env()
    name = os.environ.get("DB_NAME", "").strip()
    if not name:
        print("هشدار: DB_NAME تنظیم نشده؛ از dump خام MySQL صرف‌نظر شد.")
        return None

    target = EXPORT_DIR / f"db_backup_{stamp}.sql"
    cmd = [
        "mysqldump",
        f"--host={os.environ.get('DB_HOST', '127.0.0.1')}",
        f"--port={os.environ.get('DB_PORT', '3306')}",
        f"--user={os.environ.get('DB_USER', 'root')}",
        "--default-character-set=utf8mb4",
        "--single-transaction",
        "--routines",
        "--triggers",
        name,
    ]
    env = os.environ.copy()
    password = os.environ.get("DB_PASSWORD", "")
    if password:
        env["MYSQL_PWD"] = password

    try:
        with open(target, "w", encoding="utf-8") as out:
            result = subprocess.run(
                cmd,
                stdout=out,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
    except FileNotFoundError:
        if target.exists():
            target.unlink()
        print("هشدار: mysqldump در PATH نیست؛ فقط خروجی JSON ساخته می‌شود.")
        return None

    if result.returncode == 0:
        print(f"دامپ MySQL ساخته شد: {target}")
        return target

    if target.exists():
        target.unlink()
    print("خطا در ساخت دامپ MySQL:")
    print(result.stderr)
    return None


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
    backup_mysql_dump(stamp)
    dump_json(stamp)
    print("بکاپ به پایان رسید.")


if __name__ == "__main__":
    main()
