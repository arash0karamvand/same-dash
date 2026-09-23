"""خروجی دفتر متنی Beancount و اعتبارسنجی تراز هر سند."""

from logic.giant_books.money import money_int, rial

ROOTS = {
    "asset": "Assets",
    "liability": "Liabilities",
    "equity": "Equity",
    "revenue": "Income",
    "expense": "Expenses",
}


def _component(path):
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in str(path or ""))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-") or "X"
    if not cleaned[0].isalpha():
        cleaned = "A" + cleaned
    return cleaned


def _quote(text):
    body = (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{body}"'


def account_name(ledger, account_class, path):
    root = ROOTS.get(account_class, "Equity")
    book = ledger.id[:1].upper() + ledger.id[1:]
    return f"{root}:{book}:{_component(path)}"


def render_beancount(ledger, frame):
    lines = [
        'option "title" ' + _quote(ledger.label),
        'option "operating_currency" "IRR"',
        "1970-01-01 commodity IRR",
    ]
    if frame.empty:
        lines.append("")
        return "\n".join(lines) + "\n"
    opened = set()
    for row in frame.sort_values(["path", "account_class"]).itertuples(index=False):
        name = account_name(ledger, row.account_class, row.path)
        if name in opened:
            continue
        opened.add(name)
        lines.append(f"1970-01-01 open {name} IRR")
    lines.append("")
    ordered = frame.sort_values(["entry_date", "journal_id", "line_number"])
    for _, group in ordered.groupby(["entry_date", "journal_id"], sort=False):
        first = group.iloc[0]
        lines.append(f"{first.entry_date} * {_quote(first.description or first.document_code)}")
        lines.append(f"  document: {_quote(first.document_code)}")
        for row in group.itertuples(index=False):
            name = account_name(ledger, row.account_class, row.path)
            amount = money_int(rial(row.debit) - rial(row.credit))
            lines.append(f"  {name}  {amount} IRR")
        lines.append("")
    return "\n".join(lines)


def _builtin_errors(source):
    errors = []
    total = 0
    in_txn = False
    txn_at = ""
    for index, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if (
            not line
            or line.startswith("option ")
            or line.startswith("document:")
            or line.startswith('"')
            or " open " in f" {line} "
            or " commodity " in f" {line} "
        ):
            continue
        if " *" in line and line[0].isdigit():
            if in_txn and total != 0:
                errors.append(f"{txn_at}: جمع سند {total} است.")
            in_txn = True
            total = 0
            txn_at = f"سطر {index}"
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[-1] == "IRR":
            try:
                total += int(parts[-2])
            except ValueError:
                errors.append(f"سطر {index}: مبلغ نامعتبر است.")
    if in_txn and total != 0:
        errors.append(f"{txn_at}: جمع سند {total} است.")
    return errors


def validate_beancount(source):
    builtin = _builtin_errors(source)
    try:
        from beancount.loader import load_string
    except ImportError:
        return {"engine": "builtin", "valid": not builtin, "errors": builtin}
    _entries, errors, _options = load_string(source)
    rendered = [str(error) for error in errors[:20]]
    return {"engine": "beancount", "valid": not errors and not builtin, "errors": builtin + rendered}
