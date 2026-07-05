"""تست فیلتر فروش بر اساس روز شمسی."""

from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from logic.jalali import date_to_jalali
from logic.sales_day import filter_sales_for_jalali_day, sale_jalali_date


class SalesDayTest(TestCase):
    def _aware(self, y, m, d, hh, mm=0):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime(y, m, d, hh, mm), tz)

    def test_sale_jalali_date(self):
        from backend.models import Customer, Sale

        customer = Customer.objects.create(full_name="Ali", phone="09120000098")
        day = datetime(2026, 6, 24).date()
        jy, jm, jd = date_to_jalali(day)

        on_day = Sale.objects.create(
            customer=customer,
            amount=100,
            final_amount=100,
            sold_at=self._aware(2026, 6, 24, 14, 0),
        )
        other = Sale.objects.create(
            customer=customer,
            amount=200,
            final_amount=200,
            sold_at=self._aware(2026, 6, 25, 14, 0),
        )

        qs = filter_sales_for_jalali_day(Sale.objects.all(), jy, jm, jd)
        self.assertEqual(list(qs.values_list("id", flat=True)), [on_day.id])
        self.assertEqual(sale_jalali_date(on_day), (jy, jm, jd))
        self.assertNotEqual(sale_jalali_date(other), (jy, jm, jd))

    def test_filter_with_select_related(self):
        from backend.models import Customer, Sale

        customer = Customer.objects.create(full_name="Sara", phone="09120000099")
        day = datetime(2026, 6, 24).date()
        jy, jm, jd = date_to_jalali(day)
        on_day = Sale.objects.create(
            customer=customer,
            amount=100,
            final_amount=100,
            sold_at=self._aware(2026, 6, 24, 14, 0),
        )
        qs = Sale.objects.select_related("customer").all()
        filtered = filter_sales_for_jalali_day(qs, jy, jm, jd)
        self.assertEqual(list(filtered.values_list("id", flat=True)), [on_day.id])
