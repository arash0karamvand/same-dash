"""منطق کیف پول مشتری."""

from decimal import Decimal

from django.db import transaction

from backend.models import Customer, WalletTransaction


def wallet_transaction_to_dict(tx):
    return {
        "id": tx.id,
        "amount": int(tx.amount),
        "balance_after": int(tx.balance_after),
        "transaction_type": tx.transaction_type,
        "transaction_type_display": tx.get_transaction_type_display(),
        "description": tx.description,
        "sale_id": tx.sale_id,
        "recorded_by": tx.recorded_by.username if tx.recorded_by else None,
        "created_at": tx.created_at.isoformat(),
    }


@transaction.atomic
def adjust_wallet(customer, amount, description="", user=None, transaction_type=None, sale=None):
    """تغییر موجودی کیف پول — مبلغ مثبت=واریز، منفی=برداشت."""
    amount = Decimal(str(amount))
    if amount == 0:
        raise ValueError("مبلغ نمی‌تواند صفر باشد.")

    new_balance = customer.wallet_balance + amount
    if new_balance < 0:
        raise ValueError("موجودی کیف پول کافی نیست.")

    if not transaction_type:
        transaction_type = "deposit" if amount > 0 else "withdraw"

    customer.wallet_balance = new_balance
    customer.save(update_fields=["wallet_balance"])

    tx = WalletTransaction.objects.create(
        customer=customer,
        amount=amount,
        balance_after=new_balance,
        transaction_type=transaction_type,
        description=(description or "").strip(),
        sale=sale,
        recorded_by=user,
    )
    return tx


def get_wallet_summary(customer, limit=50):
    txs = customer.wallet_transactions.select_related("recorded_by").all()[:limit]
    return {
        "customer_id": customer.id,
        "customer_name": customer.full_name,
        "balance": int(customer.wallet_balance),
        "transactions": [wallet_transaction_to_dict(t) for t in txs],
    }
