"""endpointهای حسابداری کارخانه — /api/factory-accounting/."""

from api.helpers import api_view, fail, parse_json, success
from api.views import accounting as office_accounting
from auth.permissions import (
    APPROVE_FACTORY_ACCOUNTING,
    CREATE_FACTORY_ACCOUNTING,
    DELETE_FACTORY_ACCOUNTING,
    EDIT_FACTORY_ACCOUNTING,
    TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE,
    VIEW_FACTORY_ACCOUNTING,
    VIEW_REPORTS,
)
from logic.accounting_transfer import preview_transfer, transfer_factory_document_to_office
from logic.ledger import FACTORY_LEDGER

_LEDGER = FACTORY_LEDGER
_PERMS = {
    "view": VIEW_FACTORY_ACCOUNTING,
    "create": CREATE_FACTORY_ACCOUNTING,
    "edit": EDIT_FACTORY_ACCOUNTING,
    "delete": DELETE_FACTORY_ACCOUNTING,
    "approve": APPROVE_FACTORY_ACCOUNTING,
    "reports": VIEW_REPORTS,
}


def _bind(name):
    return office_accounting.make_view(name, ledger=_LEDGER, perms=_PERMS)


account_list = _bind("account_list")
document_models = _bind("document_models")
ledger = _bind("ledger")
entry_list = _bind("entry_list")
entry_detail = _bind("entry_detail")
entry_approve = _bind("entry_approve")
bulk_approve = _bind("bulk_approve")
summary = _bind("summary")
trial_balance = _bind("trial_balance")
detail_ledger_view = _bind("detail_ledger_view")
subsidiary_accounts = _bind("subsidiary_accounts")
detailed_accounts = _bind("detailed_accounts")
account_detail = _bind("account_detail")
subsidiary_account_detail = _bind("subsidiary_account_detail")
detailed_account_detail = _bind("detailed_account_detail")
document_list = _bind("document_list")
document_detail = _bind("document_detail")
document_approve = _bind("document_approve")
document_create = _bind("document_create")
excel_import = _bind("excel_import")


@api_view("GET", permission=TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE)
def transfer_preview(request):
    document_code = (request.GET.get("document_code") or "").strip()
    document_number = request.GET.get("document_number")
    if document_number is not None and str(document_number).strip() != "":
        try:
            document_number = int(document_number)
        except (TypeError, ValueError):
            return fail("شماره سند نامعتبر است.")
    else:
        document_number = None
    if not document_code and document_number is None:
        return fail("کد یا شماره سند الزامی است.")
    try:
        return success(
            preview_transfer(document_code=document_code, document_number=document_number)
        )
    except ValueError as exc:
        return fail(str(exc))


@api_view("POST", permission=TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE)
def transfer_document(request):
    data = parse_json(request)
    document_code = (data.get("document_code") or "").strip()
    document_number = data.get("document_number")
    if document_number is not None and str(document_number).strip() != "":
        try:
            document_number = int(document_number)
        except (TypeError, ValueError):
            return fail("شماره سند نامعتبر است.")
    else:
        document_number = None
    if not document_code and document_number is None:
        return fail("کد یا شماره سند الزامی است.")
    try:
        result = transfer_factory_document_to_office(
            document_code=document_code,
            document_number=document_number,
            user=request.user,
        )
        return success(result)
    except ValueError as exc:
        return fail(str(exc))
