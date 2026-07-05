"""تست پیامک تبریک تولد."""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from backend.models import BirthdaySmsExclusion, Customer
from logic.birthday_sms import (
    build_preview,
    customers_with_birthday_on,
    exclude_customer,
    render_birthday_message,
    send_birthday_batch,
    update_settings,
)

User = get_user_model()


class BirthdaySmsTest(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.today = today
        self.customer = Customer.objects.create(
            full_name="Ali Reza",
            phone="09121234567",
            birthday=date(1990, today.month, today.day),
        )
        Customer.objects.create(
            full_name="Other",
            phone="09129876543",
            birthday=date(1985, 1, 1),
        )
        update_settings(
            {
                "is_enabled": True,
                "message_template": "سلام {name} — {shop_name}",
                "shop_name": "سام اکسون",
                "send_time": "00:00",
            }
        )

    def test_finds_today_birthdays(self):
        qs = customers_with_birthday_on(self.today)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().full_name, "Ali Reza")

    def test_render_template(self):
        msg = render_birthday_message("سلام {name} — {shop_name}", self.customer, "سام")
        self.assertIn("Ali Reza", msg)
        self.assertIn("سام", msg)

    def test_exclude_customer(self):
        exclude_customer(self.customer.id, self.today)
        preview = build_preview(self.today)
        self.assertEqual(preview["will_send_count"], 0)
        self.assertEqual(preview["excluded_count"], 1)

    def test_send_batch(self):
        result = send_birthday_batch(for_date=self.today, force=True)
        self.assertEqual(len(result["results"]), 1)
        from backend.models import SMSLog

        log = SMSLog.objects.get(customer=self.customer, sms_type="birthday")
        self.assertEqual(log.status, "mock_sent")

    def test_build_preview_lists_recipients(self):
        preview = build_preview(self.today)
        self.assertEqual(preview["total_birthdays"], 1)
        self.assertEqual(len(preview["recipients"]), 1)
