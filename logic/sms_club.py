"""پیامک‌های خودکار و دستی باشگاه مشتریان."""

from decimal import Decimal

from backend.models import SmsClubSettings
from logic.sms import send_sms, send_sms_to_level, send_sms_to_all_active_customers, _bulk_result

TEMPLATE_VARS = {
    "common": ["name", "shop_name", "phone", "code"],
    "order_placed": ["amount", "invoice"],
    "level_up": ["level"],
    "discount": ["discount_label", "discount_amount", "discount_percent"],
}


def get_club_settings():
    return SmsClubSettings.get_solo()


def _format_discount_label(discount_type, value):
    val = Decimal(str(value or 0))
    if discount_type == "percent":
        return f"{int(val)}٪"
    return f"{int(val):,} ریال"


def render_template(template, **ctx):
    text = (template or "").strip()
    safe = {k: str(v if v is not None else "") for k, v in ctx.items()}
    try:
        return text.format(**safe)
    except KeyError:
        return text


def settings_to_dict(settings=None):
    s = settings or get_club_settings()
    return {
        "shop_name": s.shop_name,
        "auto_order_placed": s.auto_order_placed,
        "auto_welcome": s.auto_welcome,
        "auto_level_up": s.auto_level_up,
        "order_placed_template": s.order_placed_template,
        "welcome_template": s.welcome_template,
        "level_up_template": s.level_up_template,
        "discount_template": s.discount_template,
        "default_discount_type": s.default_discount_type,
        "default_discount_value": int(s.default_discount_value),
        "template_vars": TEMPLATE_VARS,
    }


def update_club_settings(data):
    s = get_club_settings()
    for field in (
        "shop_name",
        "auto_order_placed",
        "auto_welcome",
        "auto_level_up",
        "order_placed_template",
        "welcome_template",
        "level_up_template",
        "discount_template",
        "default_discount_type",
    ):
        if field in data:
            setattr(s, field, data[field])
    if "default_discount_value" in data:
        s.default_discount_value = Decimal(str(data["default_discount_value"] or 0))
    s.save()
    return s


def _base_ctx(customer, shop_name=None):
    s = get_club_settings()
    name = s.shop_name if shop_name is None else shop_name
    from logic.membership import ensure_membership_code

    ensure_membership_code(customer)
    return {
        "name": customer.full_name,
        "shop_name": name,
        "phone": customer.phone,
        "code": customer.membership_code,
    }


def maybe_send_order_placed(sale, user=None):
    s = get_club_settings()
    if not s.auto_order_placed:
        return None
    customer = sale.customer
    msg = render_template(
        s.order_placed_template,
        **_base_ctx(customer, s.shop_name),
        amount=int(sale.final_amount),
        invoice=sale.invoice_number or str(sale.id),
    )
    return send_sms(customer.phone, msg, customer=customer, sms_type="order_placed", user=user)


def maybe_send_welcome(customer, user=None):
    s = get_club_settings()
    if not s.auto_welcome:
        return None
    msg = render_template(s.welcome_template, **_base_ctx(customer, s.shop_name))
    return send_sms(customer.phone, msg, customer=customer, sms_type="welcome", user=user)


def maybe_send_level_up(customer, new_level, user=None):
    s = get_club_settings()
    if not s.auto_level_up or not new_level:
        return None
    msg = render_template(
        s.level_up_template,
        **_base_ctx(customer, s.shop_name),
        level=new_level.name,
    )
    return send_sms(customer.phone, msg, customer=customer, sms_type="level_up", user=user)


def build_discount_message(customer, discount_type, discount_value, template=None):
    s = get_club_settings()
    label = _format_discount_label(discount_type, discount_value)
    val = Decimal(str(discount_value or 0))
    return render_template(
        template or s.discount_template,
        **_base_ctx(customer, s.shop_name),
        discount_label=label,
        discount_amount=int(val) if discount_type == "amount" else 0,
        discount_percent=int(val) if discount_type == "percent" else 0,
    )


def send_discount_sms(customer, discount_type, discount_value, user=None, message=None):
    msg = message or build_discount_message(customer, discount_type, discount_value)
    return send_sms(customer.phone, msg, customer=customer, sms_type="discount", user=user)


def send_discount_bulk(
    discount_type,
    discount_value,
    user=None,
    customer_ids=None,
    level_id=None,
    send_to_all=False,
    message_template=None,
):
    from backend.models import Customer

    discount_type = discount_type or "amount"
    discount_value = Decimal(str(discount_value or 0))
    if discount_value <= 0:
        raise ValueError("مقدار تخفیف باید بزرگ‌تر از صفر باشد.")

    logs = []
    if send_to_all:
        customers = Customer.objects.filter(is_active=True)
    elif level_id:
        customers = Customer.objects.filter(is_active=True, level_id=level_id)
    elif customer_ids:
        customers = Customer.objects.filter(is_active=True, pk__in=customer_ids)
    else:
        raise ValueError("گیرنده مشخص نشده است.")

    for customer in customers:
        if message_template:
            msg = render_template(
                message_template,
                **_base_ctx(customer),
                discount_label=_format_discount_label(discount_type, discount_value),
                discount_amount=int(discount_value) if discount_type == "amount" else 0,
                discount_percent=int(discount_value) if discount_type == "percent" else 0,
            )
        else:
            msg = build_discount_message(customer, discount_type, discount_value)
        logs.append(
            send_sms(customer.phone, msg, customer=customer, sms_type="discount", user=user)
        )
    return _bulk_result(logs)
