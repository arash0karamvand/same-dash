"""خواندن گزینه‌ها و قوانین از MySQL — جایگزین CHOICES و لیست‌های hardcoded."""

from __future__ import annotations

from logic.catalog_defaults import POSTING_RULES as DEFAULT_POSTING_RULES
from logic.lookups import get_lookup_choices, lookup_label


def choice_dict(category: str) -> dict[str, str]:
    return {item["code"]: item["label"] for item in get_lookup_choices(category)}


def choice_pairs(category: str) -> list[tuple[str, str]]:
    return [(item["code"], item["label"]) for item in get_lookup_choices(category)]


def choice_options(category: str) -> list[dict]:
    return [
        {"value": item["code"], "label": item["label"], "meta": item.get("meta") or {}}
        for item in get_lookup_choices(category)
    ]


def lookup_meta(category: str, code: str) -> dict:
    for item in get_lookup_choices(category):
        if item["code"] == code:
            return item.get("meta") or {}
    return {}


def allowed_arms_for_piece(piece_kind: str) -> tuple[str, ...]:
    meta = lookup_meta("frame_piece_kind", piece_kind)
    arms = meta.get("allowed_arms") or []
    return tuple(arms)


def allowed_arms_map() -> dict[str, tuple[str, ...]]:
    result = {}
    for item in get_lookup_choices("frame_piece_kind"):
        arms = (item.get("meta") or {}).get("allowed_arms") or []
        result[item["code"]] = tuple(arms)
    return result


def seat_count_for_piece(piece_kind: str) -> int | None:
    meta = lookup_meta("frame_piece_kind", piece_kind)
    if "seat_count" in meta:
        return meta["seat_count"]
    return None


def assembly_piece_kinds() -> set[str]:
    return {
        item["code"]
        for item in get_lookup_choices("frame_piece_kind")
        if (item.get("meta") or {}).get("assembly_only")
    }


def paint_units() -> set[str]:
    return {item["code"] for item in get_lookup_choices("material_unit")}


def fabric_countries() -> set[str]:
    return {item["code"] for item in get_lookup_choices("workshop_fabric_country")}


def posting_rules(rule_name: str | None = None) -> dict | list | None:
    grouped: dict[str, list] = {}
    for item in get_lookup_choices("posting_rule"):
        lines = (item.get("meta") or {}).get("lines") or []
        grouped[item["code"]] = lines
    if not grouped:
        grouped = DEFAULT_POSTING_RULES
    if rule_name:
        return grouped.get(rule_name)
    return grouped


def payment_method_account_slug(payment_method: str) -> str | None:
    meta = lookup_meta("payment_method", payment_method)
    slug = meta.get("account_slug")
    if slug:
        return slug
    for item in get_lookup_choices("payment_method"):
        if item["code"] == payment_method:
            return (item.get("meta") or {}).get("account_slug")
    return None


def entry_type_account_slug(entry_type: str) -> str | None:
    meta = lookup_meta("journal_entry_type", entry_type)
    return meta.get("account_slug")


def payment_method_account_map() -> dict[str, str]:
    result = {}
    for item in get_lookup_choices("payment_method"):
        slug = (item.get("meta") or {}).get("account_slug")
        if slug:
            result[item["code"]] = slug
    return result


def entry_type_account_map() -> dict[str, str]:
    result = {}
    for item in get_lookup_choices("journal_entry_type"):
        slug = (item.get("meta") or {}).get("account_slug")
        if slug:
            result[item["code"]] = slug
    return result


def label_for(category: str, code: str) -> str:
    return lookup_label(category, code)
