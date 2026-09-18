"""منطق ارسال پیامک با درگاه قابل‌تعویض و ثبت صادقانه وضعیت.

تا زمانی که درگاه واقعی پیکربندی نشده باشد، وضعیت mock_sent یا
pending_provider_config برمی‌گردد — هرگز sent جعلی.
"""

import re
from importlib import import_module

from django.conf import settings
from django.utils import timezone

from backend.models import Customer, SMSLog

PHONE_PATTERN = re.compile(r"^09\d{9}$")


class BaseSmsGateway:
    """رابط پایه درگاه پیامک."""

    def send(self, phone_number, message):
        raise NotImplementedError


class MockSmsGateway(BaseSmsGateway):
    """شبیه‌سازی — پیامک واقعی ارسال نمی‌شود."""

    def send(self, phone_number, message):
        try:
            print(f"[SMS][MOCK] to={phone_number} :: {message}")
        except Exception:
            pass
        return (
            "mock_sent",
            "Gateway is in mock mode; no real SMS was sent.",
            "",
        )


class GenericHttpSmsGateway(BaseSmsGateway):
    """اسکلت درگاه HTTP — بدون ادعای ارسال تا پیاده‌سازی واقعی."""

    def send(self, phone_number, message):
        api_key = getattr(settings, "SMS_API_KEY", "")
        sender = getattr(settings, "SMS_SENDER", "")
        if not api_key or not sender:
            return (
                "pending_provider_config",
                "SMS credentials (SMS_API_KEY / SMS_SENDER) are not configured.",
                "",
            )
        return (
            "pending_provider_config",
            "Real HTTP gateway integration is not implemented yet.",
            "",
        )


def normalize_phone(phone_number):
    """نرمال‌سازی شماره موبایل ایران."""
    value = (phone_number or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("98") and len(value) == 12:
        value = "0" + value[2:]
    return value


def is_valid_phone(phone_number):
    return bool(PHONE_PATTERN.match(normalize_phone(phone_number)))


def get_gateway():
    dotted_path = getattr(settings, "SMS_GATEWAY", "logic.sms.MockSmsGateway")
    module_path, class_name = dotted_path.rsplit(".", 1)
    gateway_class = getattr(import_module(module_path), class_name)
    return gateway_class()


def _create_skipped_log(phone_number, message, customer, sms_type, user, reason):
    """ثبت پیامک ردشده به‌دلیل شماره نامعتبر."""
    return SMSLog.objects.create(
        customer=customer,
        phone_number=normalize_phone(phone_number) or (phone_number or "")[:20],
        message=message,
        sms_type=sms_type,
        status="failed",
        error_message=reason,
        created_by=user,
    )


def send_sms(phone_number, message, customer=None, sms_type="manual", user=None):
    """ارسال تکی — همیشه log می‌شود."""
    message = (message or "").strip()
    if not message:
        raise ValueError("Message text is required.")

    normalized = normalize_phone(phone_number)
    if not is_valid_phone(normalized):
        return _create_skipped_log(
            phone_number,
            message,
            customer,
            sms_type,
            user,
            "Invalid or empty phone number.",
        )

    log = SMSLog.objects.create(
        customer=customer,
        phone_number=normalized,
        message=message,
        sms_type=sms_type,
        status="pending",
        created_by=user,
    )

    gateway = get_gateway()
    try:
        status, detail, provider_response = gateway.send(normalized, message)
    except Exception as exc:
        status, detail, provider_response = "failed", str(exc), ""

    log.status = status
    log.sent_at = timezone.now() if status == "sent" else None
    log.provider_response = (provider_response or str(detail or ""))[:2000]
    if status != "sent":
        log.error_message = str(detail or "")[:2000]
    log.save()
    return log


def send_sms_to_customer(customer_id, message, user=None, sms_type="manual"):
    """ارسال به یک مشتری."""
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        raise ValueError("Customer not found.")

    log = send_sms(
        customer.phone,
        message,
        customer=customer,
        sms_type=sms_type,
        user=user,
    )
    return _single_result(log)


def send_sms_to_segment(segment_id, message, user=None, sms_type="promotion"):
    """ارسال به مشتریان فعال یک بخش RFM."""
    customers = Customer.objects.filter(
        is_active=True,
        rfm_score__segment_id=segment_id,
    )
    return _send_to_customers(customers, message, sms_type, user)


def send_sms_to_level(level_id, message, user=None, sms_type="promotion"):
    """سازگاری قدیمی — شناسه سطح همان بخش RFM است."""
    return send_sms_to_segment(level_id, message, user=user, sms_type=sms_type)


def send_sms_to_all_active_customers(message, user=None, sms_type="promotion"):
    """ارسال به همه مشتریان فعال."""
    customers = Customer.objects.filter(is_active=True)
    return _send_to_customers(customers, message, sms_type, user)


def _send_to_customers(customers, message, sms_type, user):
    message = (message or "").strip()
    if not message:
        raise ValueError("Message text is required.")

    logs = []
    for customer in customers:
        normalized = normalize_phone(customer.phone)
        if not is_valid_phone(normalized):
            logs.append(
                _create_skipped_log(
                    customer.phone,
                    message,
                    customer,
                    sms_type,
                    user,
                    "Invalid or empty phone number.",
                )
            )
            continue
        logs.append(
            send_sms(
                normalized,
                message,
                customer=customer,
                sms_type=sms_type,
                user=user,
            )
        )
    return _bulk_result(logs)


def _single_result(log):
    skipped = 1 if log.error_message == "Invalid or empty phone number." else 0
    successful = 1 if log.status == "sent" else 0
    failed = 1 if log.status == "failed" and not skipped else 0
    return {
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "results": [log],
    }


def _bulk_result(logs):
    skipped = sum(1 for log in logs if log.error_message == "Invalid or empty phone number.")
    successful = sum(1 for log in logs if log.status == "sent")
    failed = sum(
        1
        for log in logs
        if log.status == "failed" and log.error_message != "Invalid or empty phone number."
    )
    return {
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "results": logs,
    }
