"""CRUD and coverage endpoints for configurable posting-account mappings."""

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import EDIT_ACCOUNTING, VIEW_ACCOUNTING, has_permission
from backend.models import PostingAccountMapping
from logic.account_mappings import mapping_coverage, mapping_to_dict, save_mapping
from logic.ledger import LEGAL_LEDGER


@api_view("GET", "POST")
def mapping_list(request):
    permission = VIEW_ACCOUNTING if request.method == "GET" else EDIT_ACCOUNTING
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    if request.method == "POST":
        try:
            mapping = save_mapping(parse_json(request), ledger=LEGAL_LEDGER)
        except ValueError as exc:
            return fail(str(exc), status=400)
        return success(mapping_to_dict(mapping), status=201)
    rows = PostingAccountMapping.objects.filter(ledger=LEGAL_LEDGER.model).select_related("account")
    event_key = (request.GET.get("event_key") or "").strip()
    if event_key:
        rows = rows.filter(event_key=event_key)
    return success({"results": [mapping_to_dict(row) for row in rows]})


@api_view("GET", "PUT", "DELETE")
def mapping_detail(request, pk):
    permission = VIEW_ACCOUNTING if request.method == "GET" else EDIT_ACCOUNTING
    if not has_permission(request.user, permission):
        return fail("Permission denied", status=403)
    try:
        mapping = PostingAccountMapping.objects.select_related("account").get(
            pk=pk,
            ledger=LEGAL_LEDGER.model,
        )
    except PostingAccountMapping.DoesNotExist:
        return fail("نگاشت حساب یافت نشد.", status=404)
    if request.method == "GET":
        return success(mapping_to_dict(mapping))
    if request.method == "DELETE":
        mapping.delete()
        return success({"deleted": True, "id": pk})
    try:
        mapping = save_mapping(parse_json(request), mapping=mapping, ledger=LEGAL_LEDGER)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(mapping_to_dict(mapping))


@api_view("GET", permission=VIEW_ACCOUNTING)
def mapping_coverage_view(request):
    return success(mapping_coverage(ledger=LEGAL_LEDGER))
