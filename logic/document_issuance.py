"""صدور سند: تنها درگاه ثبت، ابطال پیش‌نویس و سند اصلاحی.

کنترلرهای فروش و انبار درخواست ثبت را به متدهای عمومی همین کلاس می‌دهند.
پیش از هر درج، جمع بدهکار و بستانکار سنجیده می‌شود. سند پس از ثبت نهایی
نه ویرایش می‌شود و نه حذف فیزیکی؛ اثر آن فقط با سند اصلاحی خنثی می‌شود.
پیش‌نویس با ابطال (حذف نرم) از گردش خارج می‌شود.
"""

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from backend.models import JournalEntry, JournalLine, JournalOrderLink, JournalRevision
from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER


class DocumentBalanceError(ValueError):
    """جمع بدهکار و بستانکار برابر نیست یا ردیف‌ها برای ثبت کافی نیستند."""


class PostedDocumentError(ValueError):
    """سند ثبت‌نهایی قابل ویرایش یا حذف مستقیم نیست."""


def _amount(value, label):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DocumentBalanceError(f"مقدار {label} نامعتبر است.") from exc
    if amount < 0:
        raise DocumentBalanceError(f"مقدار {label} نمی‌تواند منفی باشد.")
    return amount


def _line_amounts(line):
    if isinstance(line, JournalLine):
        return _amount(line.debit, "بدهکار"), _amount(line.credit, "بستانکار")
    return _amount(line.get("debit"), "بدهکار"), _amount(line.get("credit"), "بستانکار")


def _ledger_config(journal):
    if journal.ledger.code == FACTORY_LEDGER.id:
        return FACTORY_LEDGER
    return OFFICE_LEDGER


def _linked_order(journal, relation):
    link = journal.order_links.filter(relation_type=relation).select_related("order").first()
    return link.order if link else None


class DocumentIssuanceService:
    """لایه سرویس صدور سند برای کنترلرها و بقیه منطق تجاری."""

    def validate_balance(self, lines):
        """جمع بدهکار و بستانکار را قبل از هر ثبت برمی‌گرداند؛ در صورت اختلاف خطا می‌دهد."""
        if not isinstance(lines, (list, tuple)) or len(lines) < 2:
            raise DocumentBalanceError("سند حسابداری باید حداقل دو ردیف داشته باشد.")
        debit = Decimal(0)
        credit = Decimal(0)
        for index, line in enumerate(lines, 1):
            row_debit, row_credit = _line_amounts(line)
            if (row_debit > 0) == (row_credit > 0):
                raise DocumentBalanceError(
                    f"ردیف {index}: دقیقاً یکی از بدهکار یا بستانکار باید مثبت باشد."
                )
            debit += row_debit
            credit += row_credit
        if debit != credit:
            raise DocumentBalanceError("جمع بدهکار و بستانکار سند باید برابر باشد.")
        if debit <= 0:
            raise DocumentBalanceError("مبلغ سند باید بزرگ‌تر از صفر باشد.")
        return debit, credit

    @transaction.atomic
    def issue(
        self,
        *,
        lines,
        entry_type="manual",
        description="",
        entry_date=None,
        finalize=True,
        ledger=OFFICE_LEDGER,
        document_code="",
        document_number=None,
        user=None,
        sale=None,
        factory_order=None,
        transfer_source=None,
        branch=None,
        corrects=None,
        inventory_transaction=None,
        production_order=None,
    ):
        """سند را فقط پس از تأیید تراز می‌سازد. finalize=True یعنی ثبت نهایی و قفل شدن."""
        self.validate_balance(lines)
        from logic.accounting import _allocate_document

        when = entry_date or timezone.now()
        ledger_row, number, code = _allocate_document(
            ledger=ledger,
            entry_date=when,
            document_number=document_number,
            document_code=document_code,
        )
        actor = user if getattr(user, "is_authenticated", False) else None
        try:
            journal = JournalEntry.objects.create(
                ledger=ledger_row,
                document_number=number,
                document_code=code,
                entry_type=entry_type,
                entry_date=when,
                description=description,
                status=JournalEntry.STATUS_DRAFT,
                created_by=actor,
                transfer_source=transfer_source,
                branch=branch if branch is not None else getattr(sale, "branch", None),
                corrects=corrects,
            )
        except IntegrityError as exc:
            raise ValueError("این کد یا شماره سند قبلاً ثبت شده است.") from exc

        for index, line in enumerate(lines, 1):
            account = line["account"]
            if account.ledger_id != ledger_row.id:
                raise ValueError("همه حساب‌ها باید متعلق به دفتر سند باشند.")
            row_debit, row_credit = _line_amounts(line)
            JournalLine.objects.create(
                journal=journal,
                account=account,
                debit=row_debit,
                credit=row_credit,
                description=(line.get("description") or description or "").strip(),
                line_number=index,
                cost_center=line.get("cost_center"),
            )
        source = sale or factory_order
        if source is not None:
            JournalOrderLink.objects.create(
                journal=journal,
                order=source,
                relation_type="sale" if sale is not None else "factory_order",
            )
        from logic.accounting import _attach_origins

        _attach_origins(
            journal,
            sale=sale,
            factory_order=factory_order,
            inventory_transaction=inventory_transaction,
            production_order=production_order,
        )
        if finalize:
            self.finalize(journal, user=user)
        return journal

    def receive_sales_request(self, **kwargs):
        """درخواست ثبت سند از کنترلر فروش."""
        kwargs.setdefault("entry_type", "sale")
        kwargs.setdefault("ledger", OFFICE_LEDGER)
        return self.issue(**kwargs)

    def receive_warehouse_request(self, **kwargs):
        """درخواست ثبت سند از کنترلر انبار."""
        kwargs.setdefault("entry_type", "adjustment")
        return self.issue(**kwargs)

    @transaction.atomic
    def finalize(self, journal, *, user=None):
        """ثبت نهایی. تراز دوباره از ردیف‌های ذخیره‌شده خوانده می‌شود."""
        locked = JournalEntry.objects.select_for_update().get(pk=journal.pk)
        if locked.status == JournalEntry.STATUS_POSTED:
            raise PostedDocumentError("این سند قبلاً ثبت نهایی شده است.")
        if locked.status == JournalEntry.STATUS_VOID:
            raise PostedDocumentError("سند باطل قابل ثبت نهایی نیست.")
        stored = list(locked.lines.all())
        self.validate_balance(stored)
        snapshot = _snapshot(stored)
        locked.post()
        _revision(locked, JournalRevision.ACTION_POST, user=user, before=snapshot, after=snapshot)
        journal.status = locked.status
        journal.posted_at = locked.posted_at
        return locked

    @transaction.atomic
    def issue_correction(self, journal, *, reason, user=None):
        """سند اصلاحی معکوس. سند اصلی ثبت‌شده دست نمی‌خورد."""
        locked = JournalEntry.objects.select_for_update().get(pk=journal.pk)
        if locked.status != JournalEntry.STATUS_POSTED:
            raise PostedDocumentError("سند اصلاحی فقط برای سند ثبت‌نهایی صادر می‌شود.")
        if locked.corrections.exclude(status_ref_id=JournalEntry.STATUS_VOID).exists():
            raise PostedDocumentError("برای این سند قبلاً سند اصلاحی صادر شده است.")
        text = (reason or "").strip()
        if not text:
            raise PostedDocumentError("دلیل سند اصلاحی الزامی است.")
        original_lines = list(locked.lines.select_related("account"))
        reversed_lines = [
            {
                "account": line.account,
                "debit": line.credit,
                "credit": line.debit,
                "description": f"اصلاح {locked.document_code} — {line.description}"[:500],
                "cost_center": line.cost_center,
            }
            for line in original_lines
        ]
        correction = self.issue(
            lines=reversed_lines,
            entry_type="adjustment",
            description=f"سند اصلاحی {locked.document_code} — {text}"[:500],
            finalize=True,
            ledger=_ledger_config(locked),
            user=user,
            sale=_linked_order(locked, "sale"),
            factory_order=_linked_order(locked, "factory_order"),
            branch=locked.branch,
            corrects=locked,
        )
        _revision(
            locked,
            JournalRevision.ACTION_CORRECT,
            user=user,
            reason=text,
            before=_snapshot(original_lines),
            after=_snapshot(correction.lines.all()),
        )
        return correction

    @transaction.atomic
    def retire_draft(self, journal, *, user=None, reason=""):
        """ابطال پیش‌نویس یا سند در جریان بررسی. سند ثبت‌شده را حذف نمی‌کند."""
        locked = JournalEntry.objects.select_for_update().get(pk=journal.pk)
        if locked.status == JournalEntry.STATUS_POSTED:
            raise PostedDocumentError(
                "سند ثبت‌شده قابل حذف مستقیم نیست. سند اصلاحی صادر کنید."
            )
        if locked.status == JournalEntry.STATUS_VOID:
            return locked
        before = _snapshot(locked.lines.all())
        locked.status = JournalEntry.STATUS_VOID
        locked.posted_at = None
        locked.save(update_fields=["status", "posted_at"])
        _revision(
            locked,
            JournalRevision.ACTION_VOID,
            user=user,
            reason=reason,
            before=before,
            after=[],
        )
        journal.status = locked.status
        return locked


def _snapshot(lines):
    return [
        {
            "account_id": line.account_id,
            "debit": int(line.debit or 0),
            "credit": int(line.credit or 0),
            "description": line.description or "",
        }
        for line in lines
    ]


def _revision(journal, action, *, user=None, reason="", before=None, after=None):
    JournalRevision.objects.create(
        journal=journal,
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        reason=(reason or "").strip(),
        before_lines=before or [],
        after_lines=after or [],
    )
