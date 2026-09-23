"""endpointهای حسابداری — /api/accounting/ و کارخانه."""

from django.http import JsonResponse

from api.helpers import api_view, fail, parse_json, success
from api.serializers import accounting_to_dict, sale_to_dict
from auth.permissions import (
    APPROVE_ACCOUNTING,
    CREATE_ACCOUNTING,
    DELETE_ACCOUNTING,
    EDIT_ACCOUNTING,
    VIEW_ACCOUNTING,
    VIEW_REPORTS,
    has_permission,
)
from logic.accounting import delete_accounting_entry, is_auto_approved_accounting_user
from logic.accounting_accounts import (
    account_to_dict,
    accounts_grouped,
    create_detailed_account,
    create_subsidiary_account,
    detailed_to_dict,
    list_detailed_accounts,
    list_document_models,
    list_subsidiary_accounts,
    subsidiary_to_dict,
    update_detailed_account,
    update_general_account,
    update_subsidiary_account,
)
from logic.accounting_documents import (
    approve_accounting_document,
    submit_accounting_document,
    create_accounting_document,
    delete_accounting_document,
    get_accounting_document,
    list_accounting_documents,
    update_accounting_document,
)
from logic.accounting_entries import (
    bulk_approve_entries,
    create_entry_from_data,
    get_entry,
    list_entries,
    parse_entry_date,
    set_entry_approval,
    update_entry_from_data,
)
from logic.accounting_ledger import ledger_for_accounts, ledger_totals
from logic.accounting_reports import (
    accounting_summary,
    customer_accounting_data,
    detail_ledger_from_params,
    sales_report_data,
    trial_balance_for_level,
)
from logic.audit import log_action
from logic.ledger import OFFICE_LEDGER

DEFAULT_PERMS = {
    "view": VIEW_ACCOUNTING,
    "create": CREATE_ACCOUNTING,
    "edit": EDIT_ACCOUNTING,
    "delete": DELETE_ACCOUNTING,
    "approve": APPROVE_ACCOUNTING,
    "reports": VIEW_REPORTS,
}


def _entry_dict(entry, *, user, ledger):
    return accounting_to_dict(entry, user=user, ledger=ledger)


def make_view(name, *, ledger=OFFICE_LEDGER, perms=None):
    """ساخت view با دفتر و مجوزهای مشخص — برای اداری و کارخانه."""
    perms = perms or DEFAULT_PERMS

    if name == "meta":

        @api_view("GET", permission=perms["view"])
        def view(request):
            from logic.chart_of_accounts import accounting_meta

            return success(accounting_meta())

        return view

    if name == "account_list":

        @api_view("GET", permission=perms["view"])
        def view(request):
            return success({"accounts": accounts_grouped(ledger=ledger)})

        return view

    if name == "document_models":

        @api_view("GET", permission=perms["view"])
        def view(request):
            return success(list_document_models(request.GET, ledger=ledger))

        return view

    if name == "ledger":

        @api_view("GET", permission=perms["view"])
        def view(request):
            date_from = (request.GET.get("date_from") or "").strip() or None
            date_to = (request.GET.get("date_to") or "").strip() or None
            account_class = (request.GET.get("account_class") or "").strip() or None
            approved_only = (request.GET.get("approved_only") or "").strip().lower() in ("true", "1")

            rows = ledger_for_accounts(
                date_from=date_from,
                date_to=date_to,
                account_class=account_class,
                approved_only=approved_only,
                ledger=ledger,
            )
            totals = ledger_totals(rows)

            try:
                from logic.pagination import parse_page

                offset, limit = parse_page(request.GET)
            except (TypeError, ValueError):
                offset, limit = 0, 10

            return success(
                {
                    "results": rows[offset : offset + limit],
                    "total": len(rows),
                    "offset": offset,
                    "limit": limit,
                    "totals": totals,
                }
            )

        return view

    if name == "entry_list":

        @api_view("GET", "POST")
        def view(request):
            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)

                payload = list_entries(request.GET, ledger=ledger)
                return success(
                    {
                        "results": [_entry_dict(e, user=request.user, ledger=ledger) for e in payload["results"]],
                        "total": payload["total"],
                        "offset": payload["offset"],
                        "limit": payload["limit"],
                        "filtered_debit": payload["filtered_debit"],
                        "filtered_credit": payload["filtered_credit"],
                        "types": payload["types"],
                        "accounts": payload["accounts"],
                    }
                )

            if not has_permission(request.user, perms["create"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                entry, meta = create_entry_from_data(data, user=request.user, ledger=ledger)
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)

            if meta.get("kind") == "payment":
                sale = meta["sale"]
                log_action(
                    request.user,
                    "create",
                    f"دریافت وجه فاکتور {sale.invoice_number or sale.pk} — {meta['amount_rial']} ریال",
                    entity_type=ledger.entity_type,
                    entity_id=entry.id if entry else None,
                )
                return success(_entry_dict(entry, user=request.user, ledger=ledger), status=201)

            account = meta.get("account")
            log_action(
                request.user,
                "create",
                f"سند حسابداری {account.name if account else ''} — {int(entry.amount)}",
                entity_type=ledger.entity_type,
                entity_id=entry.id,
            )
            return success(_entry_dict(entry, user=request.user, ledger=ledger), status=201)

        return view

    if name == "entry_detail":

        @api_view("GET", "PUT", "DELETE")
        def view(request, pk):
            try:
                entry = get_entry(pk, ledger=ledger)
            except LookupError as exc:
                return fail(str(exc), status=404)

            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success(_entry_dict(entry, user=request.user, ledger=ledger))

            if request.method == "DELETE":
                if not (
                    has_permission(request.user, perms["delete"])
                    or has_permission(request.user, perms["approve"])
                ):
                    return fail("Permission denied", status=403)
                summary_text = f"{entry.get_entry_type_display()} — {int(entry.amount)}"
                sale_id = getattr(entry, "sale_id", None)
                try:
                    result = delete_accounting_entry(entry, user=request.user, ledger=ledger)
                except ValueError as exc:
                    return fail(str(exc), status=400)
                log_action(
                    request.user,
                    "delete",
                    f"حذف سند حسابداری {summary_text}"
                    + (f" (فاکتور #{sale_id})" if sale_id else "")
                    + (" — فاکتور از همه بخش‌ها حذف شد" if result.get("sale_deleted") else ""),
                    entity_type=ledger.entity_type,
                    entity_id=result.get("entry_id"),
                )
                return success(result)

            if not (
                has_permission(request.user, perms["edit"])
                or has_permission(request.user, perms["create"])
            ):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                entry, meta = update_entry_from_data(entry, data, user=request.user, ledger=ledger)
            except ValueError as exc:
                return fail(str(exc), status=400)

            if meta.get("kind") == "partial":
                log_action(
                    request.user,
                    "update",
                    f"ویرایش شرح/تاریخ سند #{entry.id}",
                    entity_type=ledger.entity_type,
                    entity_id=entry.id,
                )
            else:
                log_action(
                    request.user,
                    "update",
                    f"ویرایش سند حسابداری #{entry.id} — {int(entry.amount)}",
                    entity_type=ledger.entity_type,
                    entity_id=entry.id,
                )
            return success(_entry_dict(entry, user=request.user, ledger=ledger))

        return view

    if name == "entry_approve":

        @api_view("PUT", permission=perms["approve"])
        def view(request, pk):
            try:
                entry = get_entry(pk, ledger=ledger)
            except LookupError as exc:
                return fail(str(exc), status=404)

            data = parse_json(request)
            entry = set_entry_approval(entry, data.get("is_approved"))
            log_action(
                request.user,
                "approve" if entry.is_approved else "update",
                f"{'تایید' if entry.is_approved else 'لغو تایید'} سند حسابداری #{entry.id}",
                entity_type=ledger.entity_type,
                entity_id=entry.id,
            )
            return success(_entry_dict(entry, user=request.user, ledger=ledger))

        return view

    if name == "bulk_approve":

        @api_view("POST", permission=perms["approve"])
        def view(request):
            data = parse_json(request)
            try:
                updated = bulk_approve_entries(data.get("ids"), ledger=ledger)
            except ValueError as exc:
                return fail(str(exc), status=400)

            if updated:
                log_action(
                    request.user,
                    "approve",
                    f"تایید گروهی {updated} سند حسابداری",
                    entity_type=ledger.entity_type,
                )
            return success({"approved_count": updated})

        return view

    if name == "summary":

        @api_view("GET", permission=perms["view"])
        def view(request):
            return success(accounting_summary(request.GET, ledger=ledger))

        return view

    if name == "trial_balance":

        @api_view("GET", permission=perms["view"])
        def view(request):
            return success(trial_balance_for_level(request.GET, ledger=ledger))

        return view

    if name == "detail_ledger_view":

        @api_view("GET", permission=perms["view"])
        def view(request):
            try:
                data = detail_ledger_from_params(request.GET, user=request.user, ledger=ledger)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(data)

        return view

    if name == "subsidiary_accounts":

        @api_view("GET", "POST")
        def view(request):
            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success({"results": list_subsidiary_accounts(request.GET, ledger=ledger)})

            if not has_permission(request.user, perms["create"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                sub = create_subsidiary_account(
                    account_id=data.get("account_id"),
                    code=data.get("code"),
                    name=data.get("name"),
                    ledger=ledger,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(subsidiary_to_dict(sub), status=201)

        return view

    if name == "detailed_accounts":

        @api_view("GET", "POST")
        def view(request):
            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success({"results": list_detailed_accounts(request.GET, ledger=ledger)})

            if not has_permission(request.user, perms["create"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                detail = create_detailed_account(
                    subsidiary_id=data.get("subsidiary_id"),
                    code=data.get("code"),
                    name=data.get("name"),
                    ledger=ledger,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(detailed_to_dict(detail), status=201)

        return view

    if name == "account_detail":

        @api_view("GET", "PUT")
        def view(request, pk):
            from backend.models import Account
            AccountModel = Account
            try:
                account = AccountModel.objects.get(pk=pk, ledger__code=ledger.id, parent__isnull=True)
            except AccountModel.DoesNotExist:
                return fail("حساب کل یافت نشد.", status=404)

            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success(account_to_dict(account))

            if not has_permission(request.user, perms["edit"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                account = update_general_account(
                    account_id=pk,
                    name=data.get("name"),
                    is_active=data.get("is_active"),
                    ledger=ledger,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(account_to_dict(account))

        return view

    if name == "subsidiary_account_detail":

        @api_view("GET", "PUT")
        def view(request, pk):
            from backend.models import Account
            SubsidiaryModel = Account
            try:
                sub = SubsidiaryModel.objects.select_related("parent").get(
                    pk=pk, ledger__code=ledger.id, parent__isnull=False,
                    parent__parent__isnull=True,
                )
            except SubsidiaryModel.DoesNotExist:
                return fail("حساب معین یافت نشد.", status=404)

            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success(subsidiary_to_dict(sub))

            if not has_permission(request.user, perms["edit"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                sub = update_subsidiary_account(
                    sub_id=pk,
                    code=data.get("code"),
                    name=data.get("name"),
                    is_active=data.get("is_active"),
                    ledger=ledger,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(subsidiary_to_dict(sub))

        return view

    if name == "detailed_account_detail":

        @api_view("GET", "PUT")
        def view(request, pk):
            from backend.models import Account
            DetailedModel = Account
            try:
                detail = DetailedModel.objects.select_related("parent", "parent__parent").get(
                    pk=pk, ledger__code=ledger.id, parent__parent__isnull=False,
                    parent__parent__parent__isnull=True,
                )
            except DetailedModel.DoesNotExist:
                return fail("حساب تفصیلی یافت نشد.", status=404)

            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                return success(detailed_to_dict(detail))

            if not has_permission(request.user, perms["edit"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            try:
                detail = update_detailed_account(
                    detail_id=pk,
                    code=data.get("code"),
                    name=data.get("name"),
                    is_active=data.get("is_active"),
                    ledger=ledger,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(detailed_to_dict(detail))

        return view

    if name == "document_list":

        @api_view("GET", "POST")
        def view(request):
            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                payload = list_accounting_documents(request.GET, ledger=ledger)
                return success(payload)

            if not has_permission(request.user, perms["create"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            lines = data.get("lines") or []
            if not isinstance(lines, list) or not lines:
                return fail("حداقل یک ردیف سند لازم است.", status=400)

            entry_date_parsed = None
            if data.get("entry_date"):
                try:
                    entry_date_parsed = parse_entry_date(data["entry_date"])
                except ValueError as exc:
                    return fail(str(exc), status=400)

            document_number = data.get("document_number")
            if document_number is not None:
                try:
                    document_number = int(document_number)
                except (TypeError, ValueError):
                    return fail("شماره سند نامعتبر است.", status=400)

            try:
                result = create_accounting_document(
                    lines=lines,
                    entry_date=entry_date_parsed,
                    document_code=(data.get("document_code") or "").strip(),
                    document_number=document_number,
                    description=(data.get("description") or "").strip(),
                    is_approved=bool(data.get("is_approved", False))
                    or is_auto_approved_accounting_user(request.user, ledger=ledger),
                    entry_type=(data.get("entry_type") or "manual").strip() or "manual",
                    ledger=ledger,
                )
            except ValueError as exc:
                return fail(str(exc), status=400)

            log_action(
                request.user,
                "create",
                f"ثبت سند {result['document_number']} — {result['total_debit']} ریال",
                entity_type=ledger.entity_type,
            )
            return success(
                get_accounting_document(result["document_code"], user=request.user, ledger=ledger),
                status=201,
            )

        return view

    if name == "document_detail":

        @api_view("GET", "PUT", "DELETE")
        def view(request, document_code):
            code = (document_code or "").strip()
            if not code:
                return fail("کد سند الزامی است.", status=400)

            if request.method == "GET":
                if not has_permission(request.user, perms["view"]):
                    return fail("Permission denied", status=403)
                try:
                    payload = get_accounting_document(code, user=request.user, ledger=ledger)
                except LookupError as exc:
                    return fail(str(exc), status=404)
                return success(payload)

            if request.method == "DELETE":
                if not (
                    has_permission(request.user, perms["delete"])
                    or has_permission(request.user, perms["approve"])
                ):
                    return fail("Permission denied", status=403)
                try:
                    result = delete_accounting_document(code, user=request.user, ledger=ledger)
                except LookupError as exc:
                    return fail(str(exc), status=404)
                except ValueError as exc:
                    return fail(str(exc), status=400)
                log_action(
                    request.user,
                    "delete",
                    f"حذف سند {code}",
                    entity_type=ledger.entity_type,
                )
                return success(result)

            if not (
                has_permission(request.user, perms["edit"])
                or has_permission(request.user, perms["create"])
            ):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            lines = data.get("lines") or []
            if not isinstance(lines, list) or not lines:
                return fail("حداقل یک ردیف سند لازم است.", status=400)

            entry_date_parsed = None
            if data.get("entry_date"):
                try:
                    entry_date_parsed = parse_entry_date(data["entry_date"])
                except ValueError as exc:
                    return fail(str(exc), status=400)

            document_number = data.get("document_number")
            if document_number is not None:
                try:
                    document_number = int(document_number)
                except (TypeError, ValueError):
                    return fail("شماره سند نامعتبر است.", status=400)

            is_approved = data.get("is_approved")
            if is_approved is not None:
                is_approved = bool(is_approved)

            try:
                result = update_accounting_document(
                    code,
                    lines=lines,
                    entry_date=entry_date_parsed,
                    document_number=document_number,
                    description=(data.get("description") or "").strip(),
                    is_approved=is_approved,
                    user=request.user,
                    ledger=ledger,
                    override_reason=(data.get("override_reason") or "").strip(),
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)

            log_action(
                request.user,
                "update",
                f"ویرایش سند {code}",
                entity_type=ledger.entity_type,
            )
            return success(result)

        return view

    if name == "document_submit":

        @api_view("PUT", permission=perms["edit"])
        def view(request, document_code):
            code = (document_code or "").strip()
            if not code:
                return fail("کد سند الزامی است.", status=400)
            try:
                result = submit_accounting_document(code, user=request.user, ledger=ledger)
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(result)

        return view

    if name == "document_approve":

        @api_view("PUT", permission=perms["approve"])
        def view(request, document_code):
            code = (document_code or "").strip()
            if not code:
                return fail("کد سند الزامی است.", status=400)
            data = parse_json(request)
            try:
                result = approve_accounting_document(
                    code,
                    is_approved=data.get("is_approved"),
                    ledger=ledger,
                    user=request.user,
                )
            except LookupError as exc:
                return fail(str(exc), status=404)
            except ValueError as exc:
                return fail(str(exc), status=400)
            return success(result)

        return view

    if name == "document_create":

        @api_view("POST")
        def view(request):
            if not has_permission(request.user, perms["create"]):
                return fail("Permission denied", status=403)

            data = parse_json(request)
            lines = data.get("lines") or []
            if not isinstance(lines, list) or not lines:
                return fail("حداقل یک ردیف سند لازم است.", status=400)

            entry_date_parsed = None
            if data.get("entry_date"):
                try:
                    entry_date_parsed = parse_entry_date(data["entry_date"])
                except ValueError as exc:
                    return fail(str(exc), status=400)

            document_number = data.get("document_number")
            if document_number is not None:
                try:
                    document_number = int(document_number)
                except (TypeError, ValueError):
                    return fail("شماره سند نامعتبر است.", status=400)

            try:
                result = create_accounting_document(
                    lines=lines,
                    entry_date=entry_date_parsed,
                    document_code=(data.get("document_code") or "").strip(),
                    document_number=document_number,
                    description=(data.get("description") or "").strip(),
                    is_approved=bool(data.get("is_approved", False))
                    or is_auto_approved_accounting_user(request.user, ledger=ledger),
                    entry_type=(data.get("entry_type") or "manual").strip() or "manual",
                    ledger=ledger,
                )
            except ValueError as exc:
                return fail(str(exc), status=400)

            log_action(
                request.user,
                "create",
                f"ثبت سند {result['document_number']} — {result['total_debit']} ریال",
                entity_type=ledger.entity_type,
            )
            return success(
                {
                    "document_code": result["document_code"],
                    "document_number": result["document_number"],
                    "total_debit": result["total_debit"],
                    "total_credit": result["total_credit"],
                    "entries": [_entry_dict(e, user=request.user, ledger=ledger) for e in result["entries"]],
                },
                status=201,
            )

        return view

    if name == "excel_import":

        @api_view("POST", permission=perms["create"])
        def view(request):
            upload = request.FILES.get("file")
            if not upload:
                return fail("فایل اکسل انتخاب نشده است.", status=400)

            name = (upload.name or "").lower()
            if not name.endswith((".xlsx", ".xlsm")):
                return fail("فقط فایل‌های Excel (.xlsx) پذیرفته می‌شوند.", status=400)

            dry_run = (request.POST.get("dry_run") or "").strip().lower() in ("1", "true", "yes")
            approve = (request.POST.get("approve") or "").strip().lower() in ("1", "true", "yes")
            force = (request.POST.get("force") or "").strip().lower() in ("1", "true", "yes")

            from logic.accounting_excel_import import import_excel_file

            try:
                report = import_excel_file(
                    upload,
                    dry_run=dry_run,
                    approve=approve,
                    force=force,
                    ledger=ledger,
                )
            except ImportError:
                return fail("کتابخانه openpyxl نصب نیست. دستور: pip install openpyxl", status=500)
            except ValueError as exc:
                return fail(str(exc), status=400)
            except Exception as exc:
                return fail(f"خطا در پردازش فایل: {exc}", status=400)

            if report.get("errors"):
                return JsonResponse(
                    {"ok": False, "error": report["errors"][0], "data": report},
                    status=400,
                )

            if report.get("committed"):
                log_action(
                    request.user,
                    "create",
                    (
                        f"آپلود اکسل حسابداری — "
                        f"{report['stats'].get('journals_created', 0)} سند تراز، "
                        f"{report['stats'].get('details_created', 0)} تفصیلی جدید"
                    ),
                    entity_type=ledger.entity_type,
                )

            return success(report, status=200 if dry_run else 201)

        return view

    raise ValueError(f"Unknown accounting view: {name}")


# --- Office endpoints (default ledger) ---
meta = make_view("meta")
account_list = make_view("account_list")
document_models = make_view("document_models")
ledger = make_view("ledger")
entry_list = make_view("entry_list")
entry_detail = make_view("entry_detail")
entry_approve = make_view("entry_approve")
bulk_approve = make_view("bulk_approve")
summary = make_view("summary")
trial_balance = make_view("trial_balance")
detail_ledger_view = make_view("detail_ledger_view")
subsidiary_accounts = make_view("subsidiary_accounts")
detailed_accounts = make_view("detailed_accounts")
account_detail = make_view("account_detail")
subsidiary_account_detail = make_view("subsidiary_account_detail")
detailed_account_detail = make_view("detailed_account_detail")
document_list = make_view("document_list")
document_detail = make_view("document_detail")
document_approve = make_view("document_approve")
document_submit = make_view("document_submit")
document_create = make_view("document_create")
excel_import = make_view("excel_import")


@api_view("GET", permission=VIEW_REPORTS)
def sales_report(request):
    payload = sales_report_data(request.GET)
    return success(
        {
            "count": payload["count"],
            "total_amount": payload["total_amount"],
            "total_discount": payload["total_discount"],
            "total_final": payload["total_final"],
            "results": [sale_to_dict(s) for s in payload["sales"]],
        }
    )


@api_view("GET", permission=VIEW_REPORTS)
def customer_accounting(request, customer_id):
    try:
        payload = customer_accounting_data(customer_id)
    except LookupError as exc:
        return fail(str(exc), status=404)

    return success(
        {
            "customer_id": payload["customer_id"],
            "customer_name": payload["customer_name"],
            "sales_count": payload["sales_count"],
            "sales_total": payload["sales_total"],
            "paid_total": payload["paid_total"],
            "balance_due": payload["balance_due"],
            "accounting_entries_count": payload["accounting_entries_count"],
            "accounting_total": payload["accounting_total"],
            "sales": [sale_to_dict(s) for s in payload["sales"]],
            "entries": [accounting_to_dict(e, user=request.user) for e in payload["entries"]],
        }
    )


@api_view("GET", permission=VIEW_ACCOUNTING)
def accounting_preferences(request):
    from logic.check_accounting import get_user_accounting_preference

    return success(get_user_accounting_preference(request.user))


@api_view("GET", permission=VIEW_ACCOUNTING)
def check_accounts(request):
    from logic.accounting_accounts import account_to_dict
    from logic.check_accounting import list_check_accounts

    return success({"results": [account_to_dict(a) for a in list_check_accounts()]})
