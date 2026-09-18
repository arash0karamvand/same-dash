"""endpointهای سطوح باشگاه — /api/loyalty-levels/.

لیست خواندنی بخش‌های RFM را برمی‌گرداند تا فیلتر مشتری و پیامک قدیمی نشکنند.
"""

from backend.models import RfmSegment

from api.helpers import api_view, fail, parse_json, success
from api.serializers import rfm_segment_as_level_dict
from auth.permissions import (
    MANAGE_LOYALTY,
    MANAGE_RFM,
    SEND_SMS,
    VIEW_CUSTOMERS,
    VIEW_LOYALTY,
    VIEW_RFM,
    has_permission,
)
from logic.audit import log_action
from logic.rfm import create_segment, seed_rfm_defaults, update_segment


def _can_view(user):
    return any(
        has_permission(user, code)
        for code in (VIEW_LOYALTY, VIEW_RFM, VIEW_CUSTOMERS, SEND_SMS)
    )


def _can_manage(user):
    return has_permission(user, MANAGE_LOYALTY) or has_permission(user, MANAGE_RFM)


@api_view("GET", "POST")
def level_list(request):
    seed_rfm_defaults()
    if request.method == "GET":
        if not _can_view(request.user):
            return fail("Permission denied", status=403)
        segments = RfmSegment.objects.filter(is_active=True)
        return success({"results": [rfm_segment_as_level_dict(item) for item in segments]})

    if not _can_manage(request.user):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return fail("Level name is required", status=400)

    try:
        segment = create_segment(
            {
                "name": name,
                "color": data.get("color") or "#6366f1",
                "description": (data.get("description") or "").strip(),
                "r_scores": [1, 2, 3, 4, 5],
                "f_scores": [1, 2, 3, 4, 5],
                "m_scores": [1, 2, 3, 4, 5],
            }
        )
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "create",
        f"بخش RFM از سطوح باشگاه: {name}",
        entity_type="RfmSegment",
        entity_id=segment.id,
    )
    return success(rfm_segment_as_level_dict(segment), status=201)


@api_view("PUT", "DELETE")
def level_detail(request, pk):
    try:
        segment = RfmSegment.objects.get(pk=pk)
    except RfmSegment.DoesNotExist:
        return fail("Level not found", status=404)

    if request.method in ("PUT", "DELETE") and not _can_manage(request.user):
        return fail("Permission denied", status=403)

    if request.method == "DELETE":
        log_action(
            request.user,
            "delete",
            f"حذف بخش RFM {segment.name}",
            entity_type="RfmSegment",
            entity_id=segment.id,
        )
        segment.delete()
        return success({"deleted": True})

    data = parse_json(request)
    payload = {}
    if "name" in data:
        payload["name"] = data["name"]
    if "description" in data:
        payload["description"] = data.get("description") or ""
    if "color" in data:
        payload["color"] = data.get("color")
    if "is_active" in data:
        payload["is_active"] = bool(data.get("is_active"))
    try:
        update_segment(segment, payload)
    except ValueError as exc:
        return fail(str(exc), status=400)
    log_action(
        request.user,
        "update",
        f"ویرایش بخش RFM {segment.name}",
        entity_type="RfmSegment",
        entity_id=segment.id,
    )
    return success(rfm_segment_as_level_dict(segment))
