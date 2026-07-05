"""endpointهای کیف پول مشتری — /api/customers/<id>/wallet/."""

from decimal import Decimal, InvalidOperation

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import MANAGE_WALLET, VIEW_WALLET, has_permission
from backend.models import Customer
from logic.audit import log_action
from logic.wallet import adjust_wallet, get_wallet_summary


def _get_customer(pk):
    try:
        return Customer.objects.get(pk=pk)
    except Customer.DoesNotExist:
        return None


@api_view("GET", "POST")
def customer_wallet(request, pk):
    customer = _get_customer(pk)
    if customer is None:
        return fail("Customer not found", status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_WALLET):
            return fail("Permission denied", status=403)
        return success(get_wallet_summary(customer))

    if not has_permission(request.user, MANAGE_WALLET):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    action = (data.get("action") or "adjust").strip()
    try:
        amount = Decimal(str(data.get("amount") or 0))
    except (InvalidOperation, TypeError):
        return fail("مبلغ نامعتبر است.", status=400)

    description = (data.get("description") or "").strip()
    if action == "deposit":
        if amount <= 0:
            return fail("مبلغ واریز باید مثبت باشد.", status=400)
        tx_type = "deposit"
    elif action == "withdraw":
        if amount <= 0:
            return fail("مبلغ برداشت باید مثبت باشد.", status=400)
        amount = -amount
        tx_type = "withdraw"
    else:
        if amount == 0:
            return fail("مبلغ نمی‌تواند صفر باشد.", status=400)
        tx_type = (data.get("transaction_type") or "adjustment").strip()

    try:
        tx = adjust_wallet(
            customer,
            amount,
            description=description,
            user=request.user,
            transaction_type=tx_type,
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    sign = "+" if tx.amount >= 0 else ""
    log_action(
        request.user,
        "wallet",
        f"کیف پول {customer.full_name}: {sign}{int(tx.amount)} — موجودی {int(tx.balance_after)}",
        entity_type="Customer",
        entity_id=customer.id,
    )
    return success(get_wallet_summary(customer), status=201)
