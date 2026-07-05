# قرارداد Commitها

از الگوی [Conventional Commits](https://www.conventionalcommits.org/) استفاده می‌کنیم.

## ساختار

```
<type>(<scope>): <subject>

<body optional>

<footer optional>
```

- **type**: نوع تغییر
- **scope**: بخش پروژه (اختیاری) — مثل `api`, `auth`, `logic`, `ui`, `backend`
- **subject**: توضیح کوتاه و خلاصه (حالت امری، بدون نقطه پایانی)

## انواع (type)

| نوع | کاربرد |
| --- | --- |
| `feat` | افزودن قابلیت جدید |
| `fix` | رفع باگ |
| `refactor` | بازنویسی بدون تغییر رفتار |
| `docs` | مستندات |
| `style` | قالب‌بندی (بدون تغییر منطق) |
| `test` | افزودن/اصلاح تست |
| `chore` | کارهای جانبی (وابستگی، پیکربندی) |
| `perf` | بهبود کارایی |

## نمونه‌ها

```
feat(logic): افزودن محاسبه سطح مشتری بر اساس مجموع خرید
fix(api): اصلاح خطای اعتبارسنجی مبلغ فروش
docs(hosting): تکمیل راهنمای استقرار روی Nginx
test(logic): افزودن تست اعطای امتیاز باشگاه
```

## نسخه‌گذاری

- `feat` → افزایش نسخه minor
- `fix` → افزایش نسخه patch
- تغییر ناسازگار (`BREAKING CHANGE` در footer) → افزایش نسخه major

فایل `VERSION` و `CHANGELOG.md` با هر انتشار به‌روزرسانی می‌شوند.
