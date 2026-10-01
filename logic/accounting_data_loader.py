"""بارگذاری گزارش‌های چاپی اکسل حسابداری و تبدیل آن‌ها به جدول قابل تحلیل.

خروجی نرم‌افزارهای حسابداری ایرانی معمولاً پایگاه داده نیست: چند ردیف سربرگ،
عنوان ستون در دو ردیف، سلول ادغام‌شده و ردیف جمع دارد. AccountingDataLoader
این چیدمان را پیدا می‌کند، ردیف‌های غیرعددی را کنار می‌گذارد و ستون‌های مالی
را عددی می‌کند.

جای عنوان ستون‌ها ثابت فرض نشده است. در فایل نمونه، پنج ردیف اول سربرگ است
(یکی از آن‌ها خالی است) و عنوان‌ها در ردیف ششم و هفتم‌اند. اگر گزارش دیگری
همان عنوان‌ها را یک ردیف بالاتر یا پایین‌تر داشته باشد، همان منطق آن را پیدا
می‌کند.
"""

from __future__ import annotations

import math
import re
import sys
from numbers import Integral, Real
from pathlib import Path

import pandas as pd

TARAZ_COLUMNS = [
    "کد حساب",
    "عنوان حساب",
    "افتتاحیه بدهکار",
    "افتتاحیه بستانکار",
    "گردش بدهکار",
    "گردش بستانکار",
    "مانده بدهکار",
    "مانده بستانکار",
]
TARAZ_MONEY_COLUMNS = TARAZ_COLUMNS[2:]

RIZ_COLUMNS = [
    "تاریخ",
    "شماره سند",
    "ع",
    "شرح",
    "بدهکار",
    "بستانکار",
    "مانده",
    "تش",
]
RIZ_MONEY_COLUMNS = ["بدهکار", "بستانکار", "مانده"]
RIZ_NUMERIC_COLUMNS = ["شماره سند", "ع", *RIZ_MONEY_COLUMNS]

TARAZ_SHEET_ALIASES = {
    "تراز کل": ("تراز کل", "تراز كل"),
    "تراز معین": ("تراز معین", "تراز معين", "تراز معي"),
    "تراز تفصیلی": ("تراز تفصیلی", "تراز تفصيلي", "تراز تفصيل"),
}
RIZ_SHEET_ALIASES = ("ریز نمونه", "ريز نمونه", "ریز", "ريز")

TOTAL_LABELS = {"جمع", "جمع کل", "جمع کل دوره"}
DATE_RE = re.compile(r"(\d{4}/\d{2}/\d{2})")
DOC_RE = re.compile(r"(\d+)")
DETAIL_CODE_RE = re.compile(r"(\d{3,4}/\d+/\d+)")
_DIGIT_TRANS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MONEY_STRIP = str.maketrans("", "", ",،٬ \u00a0")


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing)


def _normalize(value) -> str:
    """یکسان‌سازی ی/ک عربی و ارقام فارسی برای مقایسه عنوان‌ها."""
    if _is_missing(value):
        return ""
    text = str(value).strip()
    text = text.replace("\u200c", "").replace("\u200f", "").replace("\ufeff", "")
    text = text.replace("ي", "ی").replace("ك", "ک").translate(_DIGIT_TRANS)
    return re.sub(r"\s+", " ", text).strip()


def _clean_title(value):
    if _is_missing(value):
        return pd.NA
    return str(value).strip()


def _clean_code(value):
    if _is_missing(value):
        return pd.NA
    if isinstance(value, bool):
        return pd.NA
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        number = float(value)
        if math.isfinite(number) and number.is_integer():
            return str(int(number))
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _parse_money(value) -> tuple[float, bool]:
    """مقدار مالی را به float تبدیل می‌کند.

    خروجی دوم می‌گوید مقدار پر بوده ولی عدد معتبری نبوده است.
    """
    if _is_missing(value):
        return 0.0, False
    if isinstance(value, bool):
        return 0.0, True
    if isinstance(value, Integral):
        return float(int(value)), False
    if isinstance(value, Real):
        number = float(value)
        if math.isnan(number):
            return 0.0, False
        if math.isinf(number):
            return 0.0, True
        return number, False

    text = _normalize(value).translate(_MONEY_STRIP)
    text = text.replace("ریال", "").replace("rial", "").strip()
    if not text or text.lower() in {"nan", "none", "-", "—"}:
        return 0.0, False
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = float(text)
    except ValueError:
        return 0.0, True
    if negative:
        number = -abs(number)
    return number, False


def _finalize_numbers(series: pd.Series) -> pd.Series:
    """اگر همه مقادیر صحیح باشند Int64 برمی‌گرداند، وگرنه Float64."""
    as_float = series.astype(float)
    whole = (as_float == as_float.round(0)) & as_float.abs().le(float(2**53))
    if bool(whole.all()):
        return as_float.astype("int64")
    return as_float


def _canonical_riz_header(value) -> str:
    text = _normalize(value).rstrip(".")
    if text.startswith("بدهکار"):
        return "بدهکار"
    if text.startswith("بستانکار"):
        return "بستانکار"
    aliases = {
        "تاریخ": "تاریخ",
        "شماره سند": "شماره سند",
        "ع": "ع",
        "شرح": "شرح",
        "مانده": "مانده",
        "تش": "تش",
    }
    return aliases.get(text, text)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


RECORD_COLUMNS = ["کد حساب", "عنوان حساب", "نوع رکورد", "بدهکار", "بستانکار"]
BALANCE_COLUMNS = ["کد حساب", "عنوان حساب", "بدهکار", "بستانکار", "مانده بدهکار", "مانده بستانکار"]


def movement_records(trial: pd.DataFrame) -> pd.DataFrame:
    """رکوردهای قابل ثبت از تراز: افتتاحیه و گردش.

    ستون‌های مانده نتیجهٔ گزارش هستند و رکورد ساخته نمی‌شود.
    """
    specs = (
        ("افتتاحیه", "افتتاحیه بدهکار", "افتتاحیه بستانکار"),
        ("گردش", "گردش بدهکار", "گردش بستانکار"),
    )
    rows: list[dict] = []
    for source in trial.to_dict("records"):
        for kind, debit_key, credit_key in specs:
            debit = source[debit_key]
            credit = source[credit_key]
            if debit:
                rows.append({
                    "کد حساب": source["کد حساب"],
                    "عنوان حساب": source["عنوان حساب"],
                    "نوع رکورد": kind,
                    "بدهکار": debit,
                    "بستانکار": 0,
                })
            if credit:
                rows.append({
                    "کد حساب": source["کد حساب"],
                    "عنوان حساب": source["عنوان حساب"],
                    "نوع رکورد": kind,
                    "بدهکار": 0,
                    "بستانکار": credit,
                })
    return pd.DataFrame(rows, columns=RECORD_COLUMNS)


def balances_from_records(records: pd.DataFrame) -> pd.DataFrame:
    """مانده را از جمع بدهکار و بستانکار رکوردها حساب می‌کند."""
    if records.empty:
        return pd.DataFrame(columns=BALANCE_COLUMNS)
    grouped = records.groupby(["کد حساب", "عنوان حساب"], as_index=False, sort=False)[
        ["بدهکار", "بستانکار"]
    ].sum()
    net = grouped["بدهکار"] - grouped["بستانکار"]
    grouped["مانده بدهکار"] = net.where(net > 0, 0)
    grouped["مانده بستانکار"] = (-net).where(net < 0, 0)
    return grouped


def _emit(message: str, *, stream=None) -> None:
    target = stream or sys.stderr
    text = message if message.endswith("\n") else f"{message}\n"
    try:
        target.write(text)
        target.flush()
    except UnicodeEncodeError:
        encoding = getattr(target, "encoding", None) or "utf-8"
        payload = text.encode(encoding, errors="replace")
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write(payload)
            buffer.flush()


class AccountingDataLoader:
    """خواندن و پاک‌سازی شیت‌های تراز و ریز نمونه از روی فایل اکسل."""

    TARAZ_COLUMNS = TARAZ_COLUMNS
    RIZ_COLUMNS = RIZ_COLUMNS

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._excel: pd.ExcelFile | None = None

    def __enter__(self) -> AccountingDataLoader:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._excel is not None:
            self._excel.close()
            self._excel = None

    def load_taraz(self, sheet_name: str = "تراز کل") -> pd.DataFrame:
        """شیت تراز کل، تراز معین یا تراز تفصیلی را به جدول هشت‌ستونی تبدیل می‌کند."""
        try:
            return self._load_taraz(sheet_name)
        except FileNotFoundError as exc:
            self._fail(str(exc))
        except Exception as exc:
            self._fail(f"خواندن شیت تراز «{sheet_name}» به‌خاطر خطای غیرمنتظره متوقف شد: {exc}")
        return _empty_frame(TARAZ_COLUMNS)

    def load_riz_nemooneh(self, sheet_name: str = "ریز نمونه") -> pd.DataFrame:
        """شیت گردش یک حساب (ریز نمونه) را به جدول سندها تبدیل می‌کند."""
        try:
            return self._load_riz(sheet_name)
        except FileNotFoundError as exc:
            self._fail(str(exc))
        except Exception as exc:
            self._fail(f"خواندن شیت ریز «{sheet_name}» به‌خاطر خطای غیرمنتظره متوقف شد: {exc}")
        return _empty_frame(RIZ_COLUMNS)

    def _load_taraz(self, sheet_name: str) -> pd.DataFrame:
        raw = self._read_sheet(sheet_name, TARAZ_SHEET_ALIASES)
        if raw is None:
            return _empty_frame(TARAZ_COLUMNS)

        resolved_name, frame = raw
        header_index = self._find_taraz_header(frame)
        if header_index is None:
            self._fail(
                f"سطر عنوان ستون‌ها (کد حساب / عنوان حساب) در شیت «{resolved_name}» پیدا نشد."
            )
            return _empty_frame(TARAZ_COLUMNS)
        if frame.shape[1] < len(TARAZ_COLUMNS):
            self._fail(
                f"شیت «{resolved_name}» فقط {frame.shape[1]} ستون دارد؛ "
                f"{len(TARAZ_COLUMNS)} ستون مالی لازم است."
            )
            return _empty_frame(TARAZ_COLUMNS)
        sample_accounts = self._sample_accounts(resolved_name, frame)

        body = frame.iloc[header_index + 1 :, : len(TARAZ_COLUMNS)].copy()
        body.columns = TARAZ_COLUMNS
        body["کد حساب"] = body["کد حساب"].map(_clean_code)
        body["عنوان حساب"] = body["عنوان حساب"].map(_clean_title)
        body = body.dropna(subset=["کد حساب", "عنوان حساب"], how="any")
        body = self._drop_total_and_subheader(body)
        invalid = self._apply_money(body, TARAZ_MONEY_COLUMNS)
        self._warn_invalid_amounts(resolved_name, invalid)
        body = body.reset_index(drop=True)
        report = self._taraz_metadata(frame, header_index, resolved_name)
        if sample_accounts:
            report["sample_accounts"] = sample_accounts
        body.attrs["report"] = report
        if body.empty:
            self._warn(f"شیت «{resolved_name}» ردیف حساب قابل استفاده ندارد.")
        return body

    def _load_riz(self, sheet_name: str) -> pd.DataFrame:
        raw = self._read_sheet(sheet_name, {"ریز نمونه": RIZ_SHEET_ALIASES})
        if raw is None:
            return _empty_frame(RIZ_COLUMNS)

        resolved_name, frame = raw
        header_index = self._find_riz_header(frame)
        if header_index is None:
            self._fail(f"سطر عنوان ستون‌های ریز (تاریخ / شماره سند) در شیت «{resolved_name}» پیدا نشد.")
            return _empty_frame(RIZ_COLUMNS)
        if frame.shape[1] < len(RIZ_COLUMNS):
            self._fail(
                f"شیت «{resolved_name}» فقط {frame.shape[1]} ستون دارد؛ "
                f"{len(RIZ_COLUMNS)} ستون لازم است."
            )
            return _empty_frame(RIZ_COLUMNS)

        headers = [_canonical_riz_header(cell) for cell in frame.iloc[header_index, : len(RIZ_COLUMNS)]]
        if headers != RIZ_COLUMNS:
            if len(set(headers)) == len(RIZ_COLUMNS) and set(RIZ_COLUMNS).issubset(headers):
                self._warn(f"ترتیب ستون‌های شیت «{resolved_name}» با الگوی معمول فرق داشت و بر اساس نام تطبیق داده شد.")
            else:
                self._warn(
                    f"عنوان ستون‌های شیت «{resolved_name}» با الگوی استاندارد یکی نبود "
                    "و ستون‌ها به ترتیب ثابت نام‌گذاری شدند."
                )
                headers = list(RIZ_COLUMNS)

        body = frame.iloc[header_index + 1 :, : len(RIZ_COLUMNS)].copy()
        body.columns = headers
        if list(body.columns) != RIZ_COLUMNS:
            body = body.reindex(columns=RIZ_COLUMNS)

        body["تاریخ"] = body["تاریخ"].map(_clean_title)
        body["شرح"] = body["شرح"].map(_clean_title)
        body = body.dropna(subset=["تاریخ"], how="any")
        total_mask = body["شرح"].map(_normalize).isin(TOTAL_LABELS)
        body = body.loc[~total_mask].copy()

        invalid = self._apply_money(body, RIZ_NUMERIC_COLUMNS)
        self._warn_invalid_amounts(resolved_name, invalid)
        for column in ("شرح", "تش"):
            body[column] = body[column].map(lambda value: "" if _is_missing(value) else str(value).strip())
        body["تاریخ"] = body["تاریخ"].map(lambda value: str(value).strip())
        body = body.reset_index(drop=True)
        body.attrs["report"] = self._riz_metadata(frame, header_index, resolved_name)
        if body.empty:
            self._warn(f"شیت «{resolved_name}» ردیف سند قابل استفاده ندارد.")
        return body

    def _read_sheet(self, sheet_name: str, alias_groups: dict) -> tuple[str, pd.DataFrame] | None:
        book = self._open()
        resolved = self._resolve_sheet(book.sheet_names, sheet_name, alias_groups)
        if resolved is None:
            available = "، ".join(book.sheet_names) or "هیچ"
            self._fail(f"شیت «{sheet_name}» پیدا نشد. شیت‌های موجود: {available}")
            return None
        frame = pd.read_excel(book, sheet_name=resolved, header=None, dtype=object)
        return resolved, frame

    def _open(self) -> pd.ExcelFile:
        if self._excel is not None:
            return self._excel
        if not self.filepath.is_file():
            raise FileNotFoundError(f"فایل پیدا نشد: {self.filepath}")
        self._excel = pd.ExcelFile(self.filepath)
        return self._excel

    def _resolve_sheet(self, sheet_names: list[str], requested: str, alias_groups: dict) -> str | None:
        normalized = {_normalize(name): name for name in sheet_names}
        candidates = [requested]
        requested_key = _normalize(requested)
        for aliases in alias_groups.values():
            alias_keys = {_normalize(alias) for alias in aliases}
            if requested_key in alias_keys:
                candidates.extend(aliases)
        seen: set[str] = set()
        for candidate in candidates:
            key = _normalize(candidate)
            if key in seen:
                continue
            seen.add(key)
            if key in normalized:
                return normalized[key]
        return None

    @staticmethod
    def _find_taraz_header(frame: pd.DataFrame) -> int | None:
        for index, row in frame.iterrows():
            first = _normalize(row.iloc[0]) if len(row) else ""
            second = _normalize(row.iloc[1]) if len(row) > 1 else ""
            if first == "کد حساب" and "عنوان" in second:
                return int(index)
        return None

    @staticmethod
    def _find_riz_header(frame: pd.DataFrame) -> int | None:
        for index, row in frame.iterrows():
            first = _normalize(row.iloc[0]) if len(row) else ""
            second = _normalize(row.iloc[1]) if len(row) > 1 else ""
            if first == "تاریخ" and "سند" in second:
                return int(index)
        return None

    def _drop_total_and_subheader(self, body: pd.DataFrame) -> pd.DataFrame:
        titles = body["عنوان حساب"].map(_normalize)
        codes = body["کد حساب"].map(_normalize)
        total_mask = titles.isin(TOTAL_LABELS) | codes.isin(TOTAL_LABELS)

        def _is_subheader(row) -> bool:
            labels = {_normalize(row[column]) for column in TARAZ_MONEY_COLUMNS}
            return "بدهکار" in labels and "بستانکار" in labels

        subheader_mask = body.apply(_is_subheader, axis=1)
        return body.loc[~total_mask & ~subheader_mask].copy()

    def _apply_money(self, body: pd.DataFrame, columns: list[str]) -> list[object]:
        invalid: list[object] = []
        for column in columns:
            numbers = []
            for value in body[column].tolist():
                number, bad = _parse_money(value)
                numbers.append(number)
                if bad:
                    invalid.append(value)
            body[column] = _finalize_numbers(pd.Series(numbers, index=body.index))
        return invalid

    def _warn_invalid_amounts(self, sheet_name: str, invalid: list[object]) -> None:
        if not invalid:
            return
        sample = invalid[0]
        self._warn(
            f"در شیت «{sheet_name}» {len(invalid)} مبلغ نامعتبر با صفر جایگزین شد. نمونه: {sample}"
        )

    def _sample_accounts(self, sheet_name: str, frame: pd.DataFrame) -> list[str]:
        """ستون اضافه گاهی فقط علامت «نمونه» است و حساب متناظر با ریز نمونه را نشان می‌دهد."""
        width = len(TARAZ_COLUMNS)
        if frame.shape[1] <= width:
            return []
        found: list[str] = []
        unexpected = False
        for _, row in frame.iterrows():
            code = _clean_code(row.iloc[0])
            for marker in row.iloc[width:]:
                if _is_missing(marker):
                    continue
                if _normalize(marker) == "نمونه" and not _is_missing(code):
                    if code not in found:
                        found.append(str(code))
                else:
                    unexpected = True
        if unexpected:
            self._warn(f"ستون‌های اضافه شیت «{sheet_name}» در جدول نهایی نیامدند.")
        return found

    @staticmethod
    def _taraz_metadata(frame: pd.DataFrame, header_index: int, sheet_name: str) -> dict:
        meta = {"sheet": sheet_name}
        for _, row in frame.iloc[:header_index].iterrows():
            for cell in row.tolist():
                text = _normalize(cell)
                if not text:
                    continue
                compact = text.replace(" ", "")
                dates = DATE_RE.findall(text)
                if "ازتاریخ" in compact and dates:
                    meta["date_from"] = dates[0]
                elif "تاتاریخ" in compact and dates:
                    meta["date_to"] = dates[-1]
                doc_match = DOC_RE.search(text)
                if doc_match and "ازسند" in compact:
                    meta["doc_from"] = doc_match.group(1)
                elif doc_match and "تاسند" in compact:
                    meta["doc_to"] = doc_match.group(1)
        return meta

    @staticmethod
    def _riz_metadata(frame: pd.DataFrame, header_index: int, sheet_name: str) -> dict:
        meta = {"sheet": sheet_name}
        for _, row in frame.iloc[:header_index].iterrows():
            text = _normalize(row.iloc[0]) if len(row) else ""
            if not text or ":" not in text:
                continue
            label, _, value = text.partition(":")
            value = value.strip(" -")
            if "کد حساب" in label and "تفصیل" in label:
                code_match = DETAIL_CODE_RE.search(text)
                if code_match:
                    meta["detailed_code"] = code_match.group(1)
            if "عنوان حساب کل" in label:
                meta["general_account"] = value
            elif "عنوان حساب معین" in label:
                meta["subsidiary_account"] = value
            elif "عنوان حساب تفصیل" in label:
                meta["detailed_account"] = value
        return meta

    def _fail(self, message: str) -> None:
        self.errors.append(message)
        _emit(message)

    def _warn(self, message: str) -> None:
        self.warnings.append(message)
        _emit(message)


if __name__ == "__main__":
    _configure_stdio()
    default_path = Path(__file__).resolve().parents[1] / "agents" / "گزارشات مالی تا31 تیر.xlsx"
    workbook_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    loader = AccountingDataLoader(workbook_path)
    try:
        taraz_kol = loader.load_taraz("تراز کل")
        riz = loader.load_riz_nemooneh()
    finally:
        loader.close()

    if loader.errors:
        raise SystemExit(1)

    records = movement_records(taraz_kol)
    balances = balances_from_records(records)
    reported_net = taraz_kol["مانده بدهکار"] - taraz_kol["مانده بستانکار"]
    calculated_net = (taraz_kol["افتتاحیه بدهکار"] - taraz_kol["افتتاحیه بستانکار"]
                      + taraz_kol["گردش بدهکار"] - taraz_kol["گردش بستانکار"])
    mismatches = int((reported_net != calculated_net).sum())
    debit_balance = balances["مانده بدهکار"].sum()
    shown = int(debit_balance) if float(debit_balance).is_integer() else debit_balance
    print(f"حساب‌های تراز کل: {len(taraz_kol)}")
    print(f"رکوردهای ثبت‌شدنی (افتتاحیه و گردش غیرصفر): {len(records)}")
    print(f"جمع مانده بدهکار محاسبه‌شده از رکوردها: {shown:,}")
    print(f"حساب‌هایی که ستون مانده فایل با این محاسبه فرق دارد: {mismatches}")

    if not riz.empty:
        running = (riz["بدهکار"] - riz["بستانکار"]).cumsum()
        final_balance = running.iloc[-1]
        final_shown = int(final_balance) if float(final_balance).is_integer() else final_balance
        print(f"رکوردهای ریز نمونه: {len(riz)}")
        print(f"مانده نهایی ریز، محاسبه‌شده از بدهکار و بستانکار: {final_shown:,}")
