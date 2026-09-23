"""صورت‌های مالی، خروجی Beancount و ارسال به Odoo / ERPNext."""

from django.http import HttpResponse

from api.helpers import api_view, fail, parse_json, success
from auth.permissions import (
    CREATE_ACCOUNTING,
    CREATE_FACTORY_ACCOUNTING,
    VIEW_ACCOUNTING,
    VIEW_FACTORY_ACCOUNTING,
)
from logic.giant_books import beancount_source, build_books, close_books, push_books
from logic.giant_books.service import parse_book_date
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER


def _dates(request, body=None):
    source = body if body is not None else request.GET
    date_from = parse_book_date(source.get("date_from"), "تاریخ شروع")
    date_to = parse_book_date(source.get("date_to"), "تاریخ پایان")
    if date_from and date_to and date_from > date_to:
        raise ValueError("تاریخ شروع بعد از تاریخ پایان است.")
    return date_from, date_to


def make_book_views(*, ledger, view_permission, create_permission):
    @api_view("GET", permission=view_permission)
    def books(request):
        try:
            date_from, date_to = _dates(request)
            return success(build_books(ledger, date_from=date_from, date_to=date_to))
        except ValueError as exc:
            return fail(str(exc))

    @api_view("GET", permission=view_permission)
    def books_beancount(request):
        try:
            date_from, date_to = _dates(request)
            source = beancount_source(ledger, date_from=date_from, date_to=date_to)
        except ValueError as exc:
            return fail(str(exc))
        response = HttpResponse(source, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{ledger.id}.beancount"'
        return response

    @api_view("POST", permission=create_permission)
    def books_close(request):
        body = parse_json(request)
        try:
            date_from, date_to = _dates(request, body)
            return success(close_books(
                ledger, date_from=date_from, date_to=date_to, user=request.user,
            ))
        except ValueError as exc:
            return fail(str(exc))

    @api_view("POST", permission=create_permission)
    def books_push(request):
        body = parse_json(request)
        try:
            date_from, date_to = _dates(request, body)
            return success(push_books(
                ledger, (body.get("target") or "").strip(), date_from=date_from, date_to=date_to,
            ))
        except ValueError as exc:
            return fail(str(exc))

    books.__name__ = f"books_{ledger.id}"
    books_beancount.__name__ = f"books_beancount_{ledger.id}"
    books_close.__name__ = f"books_close_{ledger.id}"
    books_push.__name__ = f"books_push_{ledger.id}"
    return books, books_beancount, books_close, books_push


office_books, office_books_beancount, office_books_close, office_books_push = make_book_views(
    ledger=OFFICE_LEDGER, view_permission=VIEW_ACCOUNTING, create_permission=CREATE_ACCOUNTING,
)
factory_books, factory_books_beancount, factory_books_close, factory_books_push = make_book_views(
    ledger=FACTORY_LEDGER,
    view_permission=VIEW_FACTORY_ACCOUNTING,
    create_permission=CREATE_FACTORY_ACCOUNTING,
)
