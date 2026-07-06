#!/bin/sh
set -e

cd /app

echo "Waiting for MySQL..."
python << 'PYEOF'
import os
import sys
import time

import pymysql

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "3306"))
user = os.environ.get("DB_USER", "dashboard")
password = os.environ.get("DB_PASSWORD", "")
database = os.environ.get("DB_NAME", "same_dashboard")

for attempt in range(60):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )
        conn.close()
        print("MySQL is ready.")
        sys.exit(0)
    except Exception as exc:
        print(f"MySQL not ready ({attempt + 1}/60): {exc}")
        time.sleep(2)

print("MySQL did not become ready in time.")
sys.exit(1)
PYEOF

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${RUN_SEED:-1}" = "1" ]; then
  python manage.py shell -c "from django.contrib.auth import get_user_model; from django.core.management import call_command; User=get_user_model(); call_command('setup_mysql') if not User.objects.filter(username='admin').exists() else print('Admin already exists, skip seed.')"
fi

exec "$@"
