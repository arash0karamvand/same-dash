"""endpointهای حسابداری — /api/accounting/."""

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
from logic.accounting import delete_accounting_entry, is_office_accounting_user
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
from logic.accounting_documents import create_accounting_document
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


@api_view("GET", permission=VIEW_ACCOUNTING)
def account_list(request):
    return success({"accounts": accounts_grouped()})


@api_view("GET", permission=VIEW_ACCOUNTING)
def document_models(request):
    """مدل‌های سند (حساب‌های دفتر کل) به همراه تعداد اسناد."""
    return success(list_document_models(request.GET))


@api_view("GET", permission=VIEW_ACCOUNTING)
def ledger(request):
    date_from = (request.GET.get("date_from") or "").strip() or None
    date_to = (request.GET.get("date_to") or "").strip() or None
    account_class = (request.GET.get("account_class") or "").strip() or None
    approved_only = (request.GET.get("approved_only") or "").strip().lower() in ("true", "1")

    rows = ledger_for_accounts(
        date_from=date_from,
        date_to=date_to,
        account_class=account_class,
        approved_only=approved_only,
    )
    totals = ledger_totals(rows)

    try:
        limit = min(max(1, int(request.GET.get("limit") or 20)), 500)
    except (TypeError, ValueError):
        limit = 20

    return success(
        {
            "results": rows[:limit],
            "total": len(rows),
            "limit": limit,
            "totals": totals,
        }
    )


@api_view("GET", "POST")
def entry_list(request):
    if request.method == "GET":
        if not has_permission(request.user, VIEW_ACCOUNTING):
            return fail("Permission denied", status=403)

        payload = list_entries(request.GET)
        return success(
            {
                "results": [accounting_to_dict(e, user=request.user) for e in payload["results"]],
                "total": payload["total"],
                "offset": payload["offset"],
                "limit": payload["limit"],
                "filtered_debit": payload["filtered_debit"],
                "filtered_credit": payload["filtered_credit"],
                "types": payload["types"],
                "accounts": payload["accounts"],
            }
        )

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        entry, meta = create_entry_from_data(data, user=request.user)
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
            entity_type="AccountingEntry",
            entity_id=entry.id if entry else None,
        )
        return success(accounting_to_dict(entry, user=request.user), status=201)

    account = meta.get("account")
    log_action(
        request.user,
        "create",
        f"سند حسابداری {account.name if account else ''} — {int(entry.amount)}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user), status=201)


@api_view("GET", "PUT", "DELETE")
def entry_detail(request, pk):
    try:
        entry = get_entry(pk)
    except LookupError as exc:
        return fail(str(exc), status=404)

    if request.method == "GET":
        if not has_permission(request.user, VIEW_ACCOUNTING):
            return fail("Permission denied", status=403)
        return success(accounting_to_dict(entry, user=request.user))

    if request.method == "DELETE":
        if not (
            has_permission(request.user, DELETE_ACCOUNTING)
            or has_permission(request.user, APPROVE_ACCOUNTING)
        ):
            return fail("Permission denied", status=403)
        summary_text = f"{entry.get_entry_type_display()} — {int(entry.amount)}"
        sale_id = entry.sale_id
        try:
            result = delete_accounting_entry(entry, user=request.user)
        except ValueError as exc:
            return fail(str(exc), status=400)
        log_action(
            request.user,
            "delete",
            f"حذف سند حسابداری {summary_text}"
            + (f" (فاکتور #{sale_id})" if sale_id else "")
            + (" — فاکتور از همه بخش‌ها حذف شد" if result.get("sale_deleted") else ""),
            entity_type="AccountingEntry",
            entity_id=result.get("entry_id"),
        )
        return success(result)

    if not (
        has_permission(request.user, EDIT_ACCOUNTING)
        or has_permission(request.user, CREATE_ACCOUNTING)
    ):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        entry, meta = update_entry_from_data(entry, data, user=request.user)
    except ValueError as exc:
        return fail(str(exc), status=400)

    if meta.get("kind") == "partial":
        log_action(
            request.user,
            "update",
            f"ویرایش شرح/تاریخ سند #{entry.id}",
            entity_type="AccountingEntry",
            entity_id=entry.id,
        )
    else:
        log_action(
            request.user,
            "update",
            f"ویرایش سند حسابداری #{entry.id} — {int(entry.amount)}",
            entity_type="AccountingEntry",
            entity_id=entry.id,
        )
    return success(accounting_to_dict(entry, user=request.user))


@api_view("PUT", permission=APPROVE_ACCOUNTING)
def entry_approve(request, pk):
    try:
        entry = get_entry(pk)
    except LookupError as exc:
        return fail(str(exc), status=404)

    data = parse_json(request)
    entry = set_entry_approval(entry, data.get("is_approved"))
    log_action(
        request.user,
        "approve" if entry.is_approved else "update",
        f"{'تایید' if entry.is_approved else 'لغو تایید'} سند حسابداری #{entry.id}",
        entity_type="AccountingEntry",
        entity_id=entry.id,
    )
    return success(accounting_to_dict(entry, user=request.user))


@api_view("POST", permission=APPROVE_ACCOUNTING)
def bulk_approve(request):
    """تایید گروهی اسناد — با شناسه‌ها یا همه اسناد در انتظار."""
    data = parse_json(request)
    try:
        updated = bulk_approve_entries(data.get("ids"))
    except ValueError as exc:
        return fail(str(exc), status=400)

    if updated:
        log_action(
            request.user,
            "approve",
            f"تایید گروهی {updated} سند حسابداری",
            entity_type="AccountingEntry",
        )
    return success({"approved_count": updated})


@api_view("GET", permission=VIEW_ACCOUNTING)
def summary(request):
    return success(accounting_summary(request.GET))


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
def trial_balance(request):
    return success(trial_balance_for_level(request.GET))


@api_view("GET", permission=VIEW_ACCOUNTING)
def detail_ledger_view(request):
    try:
        data = detail_ledger_from_params(request.GET)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(data)


@api_view("GET", "POST", permission=VIEW_ACCOUNTING)
def subsidiary_accounts(request):
    if request.method == "GET":
        return success({"results": list_subsidiary_accounts(request.GET)})

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        sub = create_subsidiary_account(
            account_id=data.get("account_id"),
            code=data.get("code"),
            name=data.get("name"),
        )
    except LookupError as exc:
        return fail(str(exc), status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(subsidiary_to_dict(sub), status=201)


@api_view("GET", "POST", permission=VIEW_ACCOUNTING)
def detailed_accounts(request):
    if request.method == "GET":
        return success({"results": list_detailed_accounts(request.GET)})

    if not has_permission(request.user, CREATE_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        detail = create_detailed_account(
            subsidiary_id=data.get("subsidiary_id"),
            code=data.get("code"),
            name=data.get("name"),
        )
    except LookupError as exc:
        return fail(str(exc), status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(detailed_to_dict(detail), status=201)


@api_view("GET", "PUT", permission=VIEW_ACCOUNTING)
def account_detail(request, pk):
    from backend.models import Account

    try:
        account = Account.objects.get(pk=pk)
    except Account.DoesNotExist:
        return fail("حساب کل یافت نشد.", status=404)

    if request.method == "GET":
        return success(account_to_dict(account))

    if not has_permission(request.user, EDIT_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        account = update_general_account(
            account_id=pk,
            name=data.get("name"),
            is_active=data.get("is_active"),
        )
    except LookupError as exc:
        return fail(str(exc), status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(account_to_dict(account))


@api_view("GET", "PUT", permission=VIEW_ACCOUNTING)
def subsidiary_account_detail(request, pk):
    from backend.models import SubsidiaryAccount

    try:
        sub = SubsidiaryAccount.objects.select_related("account").get(pk=pk)
    except SubsidiaryAccount.DoesNotExist:
        return fail("حساب معین یافت نشد.", status=404)

    if request.method == "GET":
        return success(subsidiary_to_dict(sub))

    if not has_permission(request.user, EDIT_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        sub = update_subsidiary_account(
            sub_id=pk,
            code=data.get("code"),
            name=data.get("name"),
            is_active=data.get("is_active"),
        )
    except LookupError as exc:
        return fail(str(exc), status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(subsidiary_to_dict(sub))


@api_view("GET", "PUT", permission=VIEW_ACCOUNTING)
def detailed_account_detail(request, pk):
    from backend.models import DetailedAccount

    try:
        detail = DetailedAccount.objects.select_related("subsidiary", "subsidiary__account").get(pk=pk)
    except DetailedAccount.DoesNotExist:
        return fail("حساب تفصیلی یافت نشد.", status=404)

    if request.method == "GET":
        return success(detailed_to_dict(detail))

    if not has_permission(request.user, EDIT_ACCOUNTING):
        return fail("Permission denied", status=403)

    data = parse_json(request)
    try:
        detail = update_detailed_account(
            detail_id=pk,
            code=data.get("code"),
            name=data.get("name"),
            is_active=data.get("is_active"),
        )
    except LookupError as exc:
        return fail(str(exc), status=404)
    except ValueError as exc:
        return fail(str(exc), status=400)
    return success(detailed_to_dict(detail))


@api_view("POST")
def document_create(request):
    if not has_permission(request.user, CREATE_ACCOUNTING):
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
            is_approved=bool(data.get("is_approved", False)) or is_office_accounting_user(request.user),
            entry_type=(data.get("entry_type") or "manual").strip() or "manual",
        )
    except ValueError as exc:
        return fail(str(exc), status=400)

    log_action(
        request.user,
        "create",
        f"ثبت سند {result['document_number']} — {result['total_debit']} ریال",
        entity_type="AccountingEntry",
    )
    return success(
        {
            "document_code": result["document_code"],
            "document_number": result["document_number"],
            "total_debit": result["total_debit"],
            "total_credit": result["total_credit"],
            "entries": [accounting_to_dict(e, user=request.user) for e in result["entries"]],
        },
        status=201,
    )


@api_view("POST", permission=CREATE_ACCOUNTING)
def excel_import(request):
    """آپلود فایل اکسل حسابداری — تراز کل/معین/تفصیلی + ریز نمونه."""
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
                f"{report['stats'].get('entries_created', 0)} سند، "
                f"{report['stats'].get('details_created', 0)} تفصیلی جدید"
            ),
            entity_type="AccountingEntry",
        )

    return success(report, status=200 if dry_run else 201)
