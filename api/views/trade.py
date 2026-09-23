"""خرید و فروش کالا — سیستم دائمی."""

from django.shortcuts import get_object_or_404

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import CREATE_ACCOUNTING, VIEW_ACCOUNTING
from backend.models import Material
from logic.trade_books import (
    kardex,
    list_trade_documents,
    post_purchase,
    post_purchase_return,
    post_sale,
    post_sale_return,
    purchase_amounts,
    take_cash_discount,
)


def _run(action, data, user):
    try:
        return success(action(data, user=user))
    except Material.DoesNotExist:
        return fail("کالا پیدا نشد.", status=404)
    except LookupError as exc:
        return fail(str(exc), status=404)
    except (ValueError, KeyError) as exc:
        return fail(str(exc))


@api_view("GET", permission=VIEW_ACCOUNTING)
def trade_list(request):
    return success({"results": list_trade_documents()})


@api_view("POST", permission=VIEW_ACCOUNTING)
def trade_preview(request):
    try:
        amounts = purchase_amounts(
            quantity=parse_json(request).get("quantity"),
            unit_price=parse_json(request).get("unit_price"),
            trade_discount=parse_json(request).get("trade_discount") or 0,
            freight=parse_json(request).get("freight") or 0,
            insurance=parse_json(request).get("insurance") or 0,
            other_cost=parse_json(request).get("other_cost") or 0,
            vat_rate=parse_json(request).get("vat_rate", 10),
        )
    except ValueError as exc:
        return fail(str(exc))
    payload = {key: (str(value) if hasattr(value, "as_tuple") else value) for key, value in amounts.items()}
    return success(payload)


@api_view("POST", permission=CREATE_ACCOUNTING)
def trade_purchase(request):
    return _run(post_purchase, parse_json(request), request.user)


@api_view("POST", permission=CREATE_ACCOUNTING)
def trade_purchase_return(request):
    return _run(post_purchase_return, parse_json(request), request.user)


@api_view("POST", permission=CREATE_ACCOUNTING)
def trade_sale(request):
    return _run(post_sale, parse_json(request), request.user)


@api_view("POST", permission=CREATE_ACCOUNTING)
def trade_sale_return(request):
    return _run(post_sale_return, parse_json(request), request.user)


@api_view("POST", permission=CREATE_ACCOUNTING)
def trade_discount(request):
    return _run(take_cash_discount, parse_json(request), request.user)


@api_view("GET", permission=VIEW_ACCOUNTING)
def trade_kardex(request):
    material_id = request.GET.get("material_id")
    if not str(material_id or "").isdigit():
        return fail("کالا را انتخاب کنید.")
    get_object_or_404(Material, pk=int(material_id))
    return success(kardex(int(material_id)))
