"""راهنمای صفحات — متن قابل ویرایش توسط مدیر سیستم در LookupOption."""

from backend.models import LookupOption
from logic.lookups import invalidate_lookup_cache

PAGE_GUIDE_CATEGORY = "page_guide"


def guide_text_from_opt(opt):
    meta = opt.meta or {}
    text = (meta.get("text") or "").strip()
    if text:
        return text
    label = (opt.label or "").strip()
    if label and label != "راهنما":
        return label
    return ""


def get_page_guides_map():
    return {
        opt.code: guide_text_from_opt(opt)
        for opt in LookupOption.objects.filter(category=PAGE_GUIDE_CATEGORY, is_active=True)
    }


def upsert_page_guide(code, text):
    code = (code or "").strip()
    if not code:
        raise ValueError("کد راهنما الزامی است.")
    text = (text or "").strip()
    snippet = text[:80] if text else "راهنما"
    opt, created = LookupOption.objects.get_or_create(
        category=PAGE_GUIDE_CATEGORY,
        code=code,
        defaults={"label": snippet, "meta": {"text": text}, "is_active": True},
    )
    if not created:
        opt.meta = {**(opt.meta or {}), "text": text}
        opt.label = snippet
        opt.is_active = True
        opt.save(update_fields=["label", "meta", "is_active"])
    invalidate_lookup_cache()
    return opt
