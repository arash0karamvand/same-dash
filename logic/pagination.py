"""صفحه‌بندی مشترک لیست‌ها — پیش‌فرض ۱۰ رکورد."""

PAGE_SIZE = 10
MAX_PAGE_SIZE = 500
PICKER_LIMIT = 500


def parse_page(params, default_limit=PAGE_SIZE):
    try:
        offset = max(0, int(params.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(params.get("limit") or default_limit)
    except (TypeError, ValueError):
        limit = default_limit
    limit = min(max(1, limit), MAX_PAGE_SIZE)
    return offset, limit


def paginate(qs, params, default_limit=PAGE_SIZE):
    """برش queryset و متادیتای total/offset/limit."""
    offset, limit = parse_page(params, default_limit)
    total = qs.count() if hasattr(qs, "count") else len(qs)
    page = list(qs[offset : offset + limit])
    return page, {"total": total, "offset": offset, "limit": limit}
