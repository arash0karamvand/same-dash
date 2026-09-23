"""منطق فرم‌های اداری - مساعده، تنخواه، جابجایی انبار، سفارش تولید، تایید کارکرد"""

from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.models import (
    AssistanceRequest,
    AttendanceConfirmation,
    PettyCashRequest,
    ProductionOrder,
    ProductionOrderLine,
    WarehouseTransfer,
    WarehouseTransferLine,
)
from logic.accounting_accounts import get_account
from logic.accounting_events import issue_event_draft, register_event
from logic.chart_of_accounts import ACCOUNT_SLUGS
from logic.ledger import LEGAL_LEDGER


# ========== Assistance Requests ==========


def list_assistance_requests(params, user=None):
    """لیست درخواست‌های مساعده با فیلتر"""
    qs = AssistanceRequest.objects.select_related("employee", "approved_by").order_by(
        "-request_date"
    )

    status = params.get("status")
    if status:
        qs = qs.filter(status=status)

    employee_id = params.get("employee_id")
    if employee_id:
        qs = qs.filter(employee_id=employee_id)

    from_date = params.get("from_date")
    if from_date:
        qs = qs.filter(request_date__gte=from_date)

    to_date = params.get("to_date")
    if to_date:
        qs = qs.filter(request_date__lte=to_date)

    return qs


def assistance_request_to_dict(obj):
    """تبدیل AssistanceRequest به dictionary"""
    return {
        "id": obj.id,
        "reference_code": obj.reference_code,
        "employee_id": obj.employee_id,
        "employee_name": obj.employee.get_full_name(),
        "national_code": obj.national_code,
        "department": obj.department,
        "amount": str(obj.amount),
        "reason": obj.reason,
        "request_date": obj.request_date.isoformat(),
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "approval_date": obj.approval_date.isoformat() if obj.approval_date else None,
        "approved_by_id": obj.approved_by_id,
        "approved_by_name": obj.approved_by.get_full_name() if obj.approved_by else None,
        "payment_date": obj.payment_date.isoformat() if obj.payment_date else None,
        "document_code": obj.journal.document_code if obj.journal_id else "",
        "notes": obj.notes,
        "created_at": obj.created_at.isoformat(),
    }


@transaction.atomic
def create_assistance_request(data, user):
    """ساخت درخواست مساعده جدید"""
    obj = AssistanceRequest.objects.create(
        employee=user,  # یا data.get('employee') برای مدیر
        national_code=data.get("national_code", ""),
        department=data.get("department", ""),
        amount=Decimal(data["amount"]),
        reason=data.get("reason", ""),
        notes=data.get("notes", ""),
    )

    from logic.audit import log_action

    log_action(
        user, "create", f"ثبت درخواست مساعده {obj.reference_code}", "AssistanceRequest", obj.id
    )

    return obj


@transaction.atomic
def update_assistance_request(obj, data, user):
    """ویرایش درخواست مساعده"""
    if obj.status != AssistanceRequest.STATUS_PENDING:
        raise ValueError("فقط درخواست‌های در انتظار قابل ویرایش هستند")

    if "amount" in data:
        obj.amount = Decimal(data["amount"])
    if "reason" in data:
        obj.reason = data["reason"]
    if "notes" in data:
        obj.notes = data["notes"]

    obj.save()

    from logic.audit import log_action

    log_action(user, "update", f"ویرایش درخواست مساعده {obj.reference_code}")

    return obj


@transaction.atomic
def approve_assistance_request(obj, user):
    """تایید درخواست مساعده"""
    if obj.status != AssistanceRequest.STATUS_PENDING:
        raise ValueError("این درخواست قبلاً پردازش شده است")

    obj.status = AssistanceRequest.STATUS_APPROVED
    obj.approved_by = user
    obj.approval_date = timezone.now().date()
    obj.save()

    from logic.audit import log_action

    log_action(user, "approve", f"تایید درخواست مساعده {obj.reference_code}")

    return obj


@transaction.atomic
def pay_assistance_request(obj, user):
    obj = AssistanceRequest.objects.select_for_update().get(pk=obj.pk)
    if obj.status != AssistanceRequest.STATUS_APPROVED:
        raise ValueError("فقط مساعده تأییدشده قابل پرداخت است.")
    advance = get_account(ACCOUNT_SLUGS.OTHER_RECEIVABLES, ledger=LEGAL_LEDGER)
    bank = get_account(ACCOUNT_SLUGS.BANK, ledger=LEGAL_LEDGER)
    description = f"پرداخت مساعده {obj.reference_code} — {obj.employee.get_full_name()}"
    event, _created = register_event(
        source_module="payroll",
        source_type="AssistanceRequest",
        source=obj.pk,
        event_type="assistance_paid",
        payload={"amount": str(obj.amount), "employee_id": obj.employee_id},
    )
    obj.journal = issue_event_draft(
        event,
        lines=[
            {"account": advance, "debit": obj.amount, "credit": 0, "description": description},
            {"account": bank, "debit": 0, "credit": obj.amount, "description": description},
        ],
        entry_type="payment",
        description=description,
        user=user,
    )
    obj.status = AssistanceRequest.STATUS_PAID
    obj.payment_date = timezone.localdate()
    obj.save(update_fields=["journal", "status", "payment_date", "updated_at"])
    return obj


# ========== Petty Cash Requests ==========


def list_petty_cash_requests(params, user=None):
    """لیست درخواست‌های تنخواه"""
    qs = PettyCashRequest.objects.select_related("requester", "approved_by").order_by(
        "-request_date"
    )

    status = params.get("status")
    if status:
        qs = qs.filter(status=status)

    return qs


def petty_cash_to_dict(obj):
    """تبدیل PettyCashRequest به dictionary"""
    return {
        "id": obj.id,
        "reference_code": obj.reference_code,
        "requester_id": obj.requester_id,
        "requester_name": obj.requester.get_full_name(),
        "amount": str(obj.amount),
        "purpose": obj.purpose,
        "request_date": obj.request_date.isoformat(),
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "approved_by_name": obj.approved_by.get_full_name() if obj.approved_by else None,
        "payment_date": obj.payment_date.isoformat() if obj.payment_date else None,
        "settlement_amount": str(obj.settlement_amount) if obj.settlement_amount else None,
        "document_code": obj.journal.document_code if obj.journal_id else "",
        "created_at": obj.created_at.isoformat(),
    }


@transaction.atomic
def create_petty_cash_request(data, user):
    """ساخت درخواست تنخواه"""
    obj = PettyCashRequest.objects.create(
        requester=user,
        amount=Decimal(data["amount"]),
        purpose=data["purpose"],
        notes=data.get("notes", ""),
    )

    from logic.audit import log_action

    log_action(user, "create", f"ثبت درخواست تنخواه {obj.reference_code}")

    return obj


@transaction.atomic
def process_petty_cash_request(obj, action, user, data=None):
    data = data or {}
    obj = PettyCashRequest.objects.select_for_update().get(pk=obj.pk)
    if action == "approve":
        if obj.status != PettyCashRequest.STATUS_PENDING:
            raise ValueError("این درخواست قبلاً پردازش شده است.")
        obj.status = PettyCashRequest.STATUS_APPROVED
        obj.approved_by = user
        obj.approval_date = timezone.localdate()
        obj.save(update_fields=["status", "approved_by", "approval_date", "updated_at"])
        return obj
    petty = get_account(ACCOUNT_SLUGS.PETTY_CASH, ledger=LEGAL_LEDGER)
    bank = get_account(ACCOUNT_SLUGS.BANK, ledger=LEGAL_LEDGER)
    if action == "pay":
        if obj.status != PettyCashRequest.STATUS_APPROVED:
            raise ValueError("فقط تنخواه تأییدشده قابل پرداخت است.")
        description = f"پرداخت تنخواه {obj.reference_code}"
        event, _created = register_event(
            source_module="treasury",
            source_type="PettyCashRequest",
            source=obj.pk,
            event_type="petty_cash_paid",
            payload={"amount": str(obj.amount)},
        )
        obj.journal = issue_event_draft(
            event,
            lines=[
                {"account": petty, "debit": obj.amount, "credit": 0, "description": description},
                {"account": bank, "debit": 0, "credit": obj.amount, "description": description},
            ],
            entry_type="payment",
            description=description,
            user=user,
        )
        obj.status = PettyCashRequest.STATUS_PAID
        obj.payment_date = timezone.localdate()
        obj.save(update_fields=["journal", "status", "payment_date", "updated_at"])
        return obj
    if action == "settle":
        if obj.status != PettyCashRequest.STATUS_PAID:
            raise ValueError("فقط تنخواه پرداخت‌شده قابل تسویه است.")
        spent = Decimal(str(data.get("settlement_amount") or 0))
        if spent < 0 or spent > obj.amount:
            raise ValueError("مبلغ تسویه تنخواه نامعتبر است.")
        returned = Decimal(obj.amount) - spent
        expense = get_account(ACCOUNT_SLUGS.ADMIN_OVERHEAD, ledger=LEGAL_LEDGER)
        lines = []
        if spent:
            lines.extend([
                {"account": expense, "debit": spent, "credit": 0, "description": f"هزینه تنخواه {obj.reference_code}"},
                {"account": petty, "debit": 0, "credit": spent, "description": f"تسویه تنخواه {obj.reference_code}"},
            ])
        if returned:
            lines.extend([
                {"account": bank, "debit": returned, "credit": 0, "description": f"برگشت مانده تنخواه {obj.reference_code}"},
                {"account": petty, "debit": 0, "credit": returned, "description": f"برگشت مانده تنخواه {obj.reference_code}"},
            ])
        event, _created = register_event(
            source_module="treasury",
            source_type="PettyCashRequest",
            source=obj.pk,
            event_type="petty_cash_settled",
            payload={"spent": str(spent), "returned": str(returned)},
        )
        issue_event_draft(
            event,
            lines=lines,
            entry_type="adjustment",
            description=f"تسویه تنخواه {obj.reference_code}",
            user=user,
        )
        obj.status = PettyCashRequest.STATUS_SETTLED
        obj.settlement_date = timezone.localdate()
        obj.settlement_amount = spent
        obj.settlement_notes = (data.get("settlement_notes") or "").strip()
        obj.save(update_fields=[
            "status", "settlement_date", "settlement_amount", "settlement_notes", "updated_at"
        ])
        return obj
    raise ValueError("عملیات تنخواه نامعتبر است.")


# ========== Warehouse Transfers ==========


def list_warehouse_transfers(params, user=None):
    """لیست جابجایی‌های انبار"""
    qs = WarehouseTransfer.objects.select_related(
        "from_warehouse", "to_warehouse", "requested_by"
    ).order_by("-transfer_date")

    status = params.get("status")
    if status:
        qs = qs.filter(status=status)

    return qs


def warehouse_transfer_to_dict(obj):
    """تبدیل WarehouseTransfer به dictionary"""
    return {
        "id": obj.id,
        "reference_code": obj.reference_code,
        "from_warehouse_id": obj.from_warehouse_id,
        "from_warehouse_name": obj.from_warehouse.name,
        "to_warehouse_id": obj.to_warehouse_id,
        "to_warehouse_name": obj.to_warehouse.name,
        "transfer_date": obj.transfer_date.isoformat(),
        "required_personnel": obj.required_personnel,
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "qc_approved": obj.qc_approved,
        "has_defects": obj.has_defects,
        "lines": [
            {
                "line_number": line.line_number,
                "product_code": line.product_code,
                "product_description": line.product_description,
                "quantity": str(line.quantity),
                "unit": line.unit,
            }
            for line in obj.lines.all()
        ],
        "created_at": obj.created_at.isoformat(),
    }


@transaction.atomic
def create_warehouse_transfer(data, user):
    """ساخت جابجایی انبار"""
    from backend.models import Warehouse

    obj = WarehouseTransfer.objects.create(
        from_warehouse=Warehouse.objects.get(pk=data["from_warehouse_id"]),
        to_warehouse=Warehouse.objects.get(pk=data["to_warehouse_id"]),
        transfer_date=data["transfer_date"],
        required_personnel=data.get("required_personnel", 1),
        requested_by=user,
        notes=data.get("notes", ""),
    )

    # ساخت آیتم‌ها
    for idx, line_data in enumerate(data.get("lines", []), 1):
        WarehouseTransferLine.objects.create(
            transfer=obj,
            line_number=idx,
            product_code=line_data["product_code"],
            product_description=line_data["product_description"],
            quantity=Decimal(line_data["quantity"]),
            unit=line_data.get("unit", "عدد"),
            notes=line_data.get("notes", ""),
        )

    from logic.audit import log_action

    log_action(user, "create", f"ثبت جابجایی انبار {obj.reference_code}")

    return obj


# ========== Production Orders ==========


def list_production_orders(params, user=None):
    """لیست سفارشات تولید"""
    qs = ProductionOrder.objects.select_related("sale", "created_by").order_by(
        "-delivery_date"
    )

    status = params.get("status")
    if status:
        qs = qs.filter(status=status)

    priority = params.get("priority")
    if priority:
        qs = qs.filter(priority=priority)

    return qs


def production_order_to_dict(obj):
    """تبدیل ProductionOrder به dictionary"""
    return {
        "id": obj.id,
        "reference_code": obj.reference_code,
        "sale_id": obj.sale_id,
        "invoice_number": obj.invoice_number,
        "customer_name": obj.customer_name,
        "order_type": obj.order_type,
        "order_type_label": obj.get_order_type_display(),
        "order_date": obj.order_date.isoformat(),
        "delivery_date": obj.delivery_date.isoformat(),
        "priority": obj.priority,
        "priority_label": obj.get_priority_display(),
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "product_model": obj.product_model,
        "lines": [
            {
                "line_number": line.line_number,
                "quantity": line.quantity,
                "wood_color": line.wood_color,
                "fabric_color": line.fabric_color,
                "fabric_code": line.fabric_code,
            }
            for line in obj.lines.all()
        ],
        "created_at": obj.created_at.isoformat(),
    }


@transaction.atomic
def create_production_order(data, user):
    """ساخت سفارش تولید"""
    obj = ProductionOrder.objects.create(
        sale_id=data.get("sale_id"),
        invoice_number=data.get("invoice_number", ""),
        customer_name=data["customer_name"],
        order_type=data.get("order_type", ProductionOrder.ORDER_TYPE_PRODUCTION),
        delivery_date=data["delivery_date"],
        priority=data.get("priority", ProductionOrder.PRIORITY_WHITE),
        product_model=data.get("product_model", ""),
        product_name=data.get("product_name", ""),
        cushion_notes=data.get("cushion_notes", ""),
        general_notes=data.get("general_notes", ""),
        created_by=user,
    )

    # ساخت آیتم‌ها
    for line_data in data.get("lines", []):
        ProductionOrderLine.objects.create(
            production_order=obj,
            line_number=line_data["line_number"],
            quantity=line_data.get("quantity", 1),
            wood_color=line_data.get("wood_color", ""),
            panel_color=line_data.get("panel_color", ""),
            fabric_color=line_data.get("fabric_color", ""),
            fabric_quality=line_data.get("fabric_quality", ""),
            fabric_code=line_data.get("fabric_code", ""),
        )

    from logic.audit import log_action

    log_action(user, "create", f"ثبت سفارش تولید {obj.reference_code}")

    return obj


# ========== Attendance Confirmations ==========


def list_attendance_confirmations(params, user=None):
    """لیست تاییدیه‌های کارکرد"""
    qs = AttendanceConfirmation.objects.select_related("employee", "confirmed_by").order_by(
        "-year", "-month_number"
    )

    status = params.get("status")
    if status:
        qs = qs.filter(status=status)

    year = params.get("year")
    if year:
        qs = qs.filter(year=int(year))

    return qs


def attendance_confirmation_to_dict(obj):
    """تبدیل AttendanceConfirmation به dictionary"""
    return {
        "id": obj.id,
        "reference_code": obj.reference_code,
        "employee_id": obj.employee_id,
        "employee_name": obj.employee.get_full_name(),
        "month": obj.month,
        "days_worked": obj.days_worked,
        "overtime_hours": str(obj.overtime_hours),
        "absence_days": obj.absence_days,
        "leave_days": obj.leave_days,
        "status": obj.status,
        "status_label": obj.get_status_display(),
        "confirmed_by_name": obj.confirmed_by.get_full_name() if obj.confirmed_by else None,
        "created_at": obj.created_at.isoformat(),
    }


@transaction.atomic
def create_attendance_confirmation(data, user):
    """ساخت تاییدیه کارکرد"""
    month = data["month"]  # Format: "1403-09"
    year, month_number = month.split("-")

    obj = AttendanceConfirmation.objects.create(
        employee=user,
        month=month,
        year=int(year),
        month_number=int(month_number),
        days_worked=data["days_worked"],
        overtime_hours=Decimal(data.get("overtime_hours", 0)),
        absence_days=data.get("absence_days", 0),
        leave_days=data.get("leave_days", 0),
        notes=data.get("notes", ""),
    )

    from logic.audit import log_action

    log_action(user, "create", f"ثبت کارکرد {month}")

    return obj
