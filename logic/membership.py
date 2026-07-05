"""کد عضویت باشگاه مشتریان."""

import secrets

from backend.models import Customer


def generate_membership_code():
    """کد ۸ رقمی یکتا برای باشگاه."""
    for _ in range(50):
        code = "".join(secrets.choice("0123456789") for _ in range(8))
        if not Customer.objects.filter(membership_code=code).exists():
            return code
    raise RuntimeError("امکان تولید کد عضویت یکتا وجود ندارد.")


def ensure_membership_code(customer):
    if customer.membership_code:
        return customer.membership_code
    customer.membership_code = generate_membership_code()
    customer.save(update_fields=["membership_code", "updated_at"])
    return customer.membership_code
