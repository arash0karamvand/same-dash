"""پیکربندی دیتابیس Django — فقط MySQL."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def load_env_file(base_dir):
    """بارگذاری متغیرهای .env در ریشه پروژه (بدون override مقادیر موجود)."""
    env_path = Path(base_dir) / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _mysql_database():
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError as exc:
        raise ImproperlyConfigured(
            "برای MySQL پکیج PyMySQL لازم است: pip install PyMySQL"
        ) from exc

    name = os.environ.get("DB_NAME", "").strip()
    if not name:
        raise ImproperlyConfigured(
            "برای MySQL متغیر DB_NAME را در .env تنظیم کنید."
        )

    return {
        "default": {
            "ENGINE": "backend.db_backends.compat_mysql",
            "NAME": name,
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": (
                    "SET sql_mode='STRICT_TRANS_TABLES,"
                    "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
                ),
            },
            # Django creates the test schema itself.  Declaring the charset is
            # essential on MySQL/MariaDB servers whose global default is latin1;
            # otherwise Persian reference-data seeds fail during migration.
            "TEST": {
                "CHARSET": "utf8mb4",
                "COLLATION": "utf8mb4_unicode_ci",
            },
        }
    }


def build_databases(base_dir):
    """ساخت تنظیمات DATABASES — فقط MySQL."""
    del base_dir
    engine = os.environ.get("DB_ENGINE", "mysql").strip().lower()
    if engine in ("", "mysql", "mariadb"):
        return _mysql_database()

    raise ImproperlyConfigured(
        f"این پروژه فقط MySQL را پشتیبانی می‌کند. DB_ENGINE={engine!r} مجاز نیست."
    )
