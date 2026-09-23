"""پل خروجی به Odoo (account.move) و ERPNext (Journal Entry).

این دو سیستم داخل جنگو نصب نمی‌شوند. سند آماده ساخته می‌شود و فقط وقتی
نشانی و رمز در محیط باشد، به همان API رسمی‌شان فرستاده می‌شود.
"""

import json
import os
import urllib.error
import urllib.request
import xmlrpc.client

from logic.giant_books.money import money_int, rial


def _moves(frame):
    if frame.empty:
        return []
    moves = []
    ordered = frame.sort_values(["entry_date", "journal_id", "line_number"])
    for _, group in ordered.groupby("journal_id", sort=False):
        first = group.iloc[0]
        lines = []
        for row in group.itertuples(index=False):
            lines.append({
                "account_code": str(row.code),
                "name": (row.description or row.name or "")[:200],
                "debit": money_int(rial(row.debit)),
                "credit": money_int(rial(row.credit)),
            })
        moves.append({
            "move_type": "entry",
            "date": str(first.entry_date),
            "ref": str(first.document_code),
            "narration": str(first.description or ""),
            "line_ids": lines,
        })
    return moves


def odoo_configured():
    return all(os.environ.get(key) for key in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_PASSWORD"))


def erpnext_configured():
    return all(os.environ.get(key) for key in ("ERPNEXT_URL", "ERPNEXT_API_KEY", "ERPNEXT_API_SECRET"))


def odoo_moves(frame):
    return _moves(frame)


def erpnext_entries(frame, *, company=None, company_abbr=None):
    company = company or os.environ.get("ERPNEXT_COMPANY") or "شرکت"
    company_abbr = company_abbr or os.environ.get("ERPNEXT_COMPANY_ABBR") or "CO"
    entries = []
    for move in _moves(frame):
        accounts = []
        for line in move["line_ids"]:
            accounts.append({
                "account": f"{line['account_code']} - {company_abbr}",
                "account_code": line["account_code"],
                "debit_in_account_currency": line["debit"],
                "credit_in_account_currency": line["credit"],
            })
        entries.append({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": company,
            "posting_date": move["date"],
            "user_remark": move["narration"] or move["ref"],
            "cheque_no": move["ref"],
            "accounts": accounts,
        })
    return entries


def push_odoo(moves):
    if not odoo_configured():
        raise ValueError(
            "اتصال Odoo تنظیم نشده است. ODOO_URL، ODOO_DB، ODOO_USER و ODOO_PASSWORD را قرار دهید."
        )
    url = os.environ["ODOO_URL"].rstrip("/")
    db = os.environ["ODOO_DB"]
    user = os.environ["ODOO_USER"]
    password = os.environ["ODOO_PASSWORD"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise ValueError("ورود به Odoo ناموفق بود.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    journal_id = (os.environ.get("ODOO_JOURNAL_ID") or "").strip()
    created = []
    for move in moves:
        commands = []
        for line in move["line_ids"]:
            found = models.execute_kw(
                db, uid, password, "account.account", "search",
                [[["code", "=", line["account_code"]]]], {"limit": 1},
            )
            if not found:
                raise ValueError(f"حساب {line['account_code']} در Odoo پیدا نشد.")
            commands.append((0, 0, {
                "account_id": found[0],
                "name": line["name"],
                "debit": line["debit"],
                "credit": line["credit"],
            }))
        values = {
            "move_type": "entry",
            "date": move["date"],
            "ref": move["ref"],
            "line_ids": commands,
        }
        if journal_id:
            values["journal_id"] = int(journal_id)
        created.append(models.execute_kw(db, uid, password, "account.move", "create", [values]))
    return {"target": "odoo", "count": len(created), "created": created}


def push_erpnext(entries):
    if not erpnext_configured():
        raise ValueError(
            "اتصال ERPNext تنظیم نشده است. ERPNEXT_URL، ERPNEXT_API_KEY و ERPNEXT_API_SECRET را قرار دهید."
        )
    url = os.environ["ERPNEXT_URL"].rstrip("/")
    token = f"{os.environ['ERPNEXT_API_KEY']}:{os.environ['ERPNEXT_API_SECRET']}"
    created = []
    for entry in entries:
        request = urllib.request.Request(
            f"{url}/api/resource/Journal%20Entry",
            data=json.dumps(entry).encode("utf-8"),
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise ValueError(f"ERPNext سند را نپذیرفت: {detail}") from exc
        created.append((body.get("data") or {}).get("name") or "")
    return {"target": "erpnext", "count": len(created), "created": created}
