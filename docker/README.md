# Docker — same-dash

## پیش‌نیاز

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ویندوز/Mac)
- یا Docker + Docker Compose روی Linux

## راه‌اندازی سریع

```bash
cp .env.docker.example .env
docker compose up -d --build
```

سایت: **http://localhost:8080**

| کاربر | رمز |
|--------|-----|
| `admin` | `admin1234` |

## دستورات مفید

```bash
# وضعیت
docker compose ps

# لاگ‌ها
docker compose logs -f backend

# توقف
docker compose down

# توقف + حذف دیتابیس
docker compose down -v
```

## متغیرهای مهم (.env)

| متغیر | توضیح |
|--------|--------|
| `HTTP_PORT` | پورت nginx (پیش‌فرض 8080) |
| `DB_PASSWORD` | رمز کاربر MySQL |
| `DJANGO_SECRET_KEY` | کلید Django |
| `SESSION_COOKIE_SECURE` | برای HTTPS: `true` |
| `RUN_SEED` | `0` در production بعد از اولین اجرا |

## production

1. `DJANGO_DEBUG=False`
2. `DJANGO_SECRET_KEY` تصادفی
3. `SESSION_COOKIE_SECURE=true` + HTTPS جلوی nginx
4. `RUN_SEED=0` بعد از ساخت admin
