"""توابع تبدیل مدل به دیکشنری (سریالایز دستی، جایگزین DRF Serializers).

هر تابع یک شیء مدل را به دیکشنری قابل‌تبدیل به JSON نگاشت می‌کند.
"""


def level_to_dict(level):
    if level is None:
        return None
    return {
        "id": level.id,
        "name": level.name,
        "min_purchase": int(level.min_purchase),
        "max_purchase": int(level.max_purchase) if level.max_purchase is not None else None,
        "discount_percent": float(level.discount_percent),
        "points": level.points,
        "description": level.description,
        "color": level.color,
        "is_active": level.is_active,
    }


def customer_to_dict(customer):
    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "membership_code": customer.membership_code or "",
        "email": customer.email,
        "address": customer.address or "",
        "level": level_to_dict(customer.level),
        "total_purchases": int(customer.total_purchases),
        "last_purchase_at": customer.last_purchase_at.isoformat() if customer.last_purchase_at else None,
        "notes": customer.notes,
        "is_active": customer.is_active,
        "joined_at": customer.joined_at.isoformat(),
        "birthday": customer.birthday.isoformat() if customer.birthday else None,
        "wallet_balance": int(customer.wallet_balance),
    }


def line_item_to_dict(item, user=None):
    from auth.org_roles import should_mask_amounts_for_user, should_mask_prices_for_user

    mask_prices = user and should_mask_prices_for_user(user)
    mask_amounts = user and should_mask_amounts_for_user(user)
    hide_money = mask_prices or mask_amounts
    return {
        "id": item.id,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "product_name": item.product_name,
        "product_model": item.product_model or "",
        "fabric": item.fabric or "",
        "color_name": item.color_name or "",
        "color_hex": item.color_hex or "",
        "quantity": item.quantity,
        "unit_price": None if hide_money else int(item.unit_price),
        "line_total": None if hide_money else int(item.line_total),
        "prices_masked": hide_money,
    }


def sale_to_dict(sale, include_installments=False, include_lines=False, user=None):
    from auth.org_roles import (
        should_mask_amounts_for_user,
        should_mask_customer_for_sale,
        should_mask_prices_for_user,
    )
    from logic.branches import branch_labels
    from logic.sale_workflow import WORKFLOW_STAGE_LABELS

    BRANCH_LABELS = branch_labels()

    paid = int(sale.paid_amount)
    final = int(sale.final_amount)
    mask_customer = user and should_mask_customer_for_sale(user, sale)
    mask_prices = user and should_mask_prices_for_user(user)
    mask_amounts = user and should_mask_amounts_for_user(user)
    hide_money = mask_prices or mask_amounts
    data = {
        "id": sale.id,
        "customer_id": None if mask_customer else sale.customer_id,
        "customer_name": "—" if mask_customer else sale.customer.full_name,
        "customer_phone": "" if mask_customer else (sale.customer.phone if sale.customer_id else ""),
        "customer_address": "" if mask_customer else (sale.customer.address or ""),
        "customer_wallet_balance": 0 if mask_customer else (int(sale.customer.wallet_balance) if sale.customer_id else 0),
        "customer_masked": mask_customer,
        "amount": None if hide_money else int(sale.amount),
        "discount_type": sale.discount_type,
        "discount_type_display": sale.get_discount_type_display(),
        "discount_value": None if hide_money else int(sale.discount_value),
        "discount": None if hide_money else int(sale.discount),
        "final_amount": None if hide_money else final,
        "paid_amount": None if hide_money else paid,
        "balance_due": None if hide_money else max(0, final - paid),
        "amounts_masked": hide_money,
        "prices_masked": mask_prices,
        "sold_at": sale.sold_at.isoformat(),
        "invoice_number": sale.invoice_number,
        "description": sale.description,
        "payment_status": sale.payment_status,
        "payment_status_display": sale.get_payment_status_display(),
        "payment_method": sale.payment_method,
        "payment_method_display": sale.get_payment_method_display(),
        "accounting_mode": sale.accounting_mode,
        "accounting_mode_display": sale.get_accounting_mode_display(),
        "recorded_by": sale.recorded_by.username if sale.recorded_by else None,
        "branch": sale.branch or "",
        "branch_label": BRANCH_LABELS.get(sale.branch, "—"),
        "seller_name": sale.seller.full_name if sale.seller_id else None,
        "order_kind": sale.order_kind,
        "order_kind_display": sale.get_order_kind_display(),
        "order_status": sale.order_status,
        "order_status_display": sale.get_order_status_display(),
        "workflow_stage": sale.workflow_stage,
        "workflow_stage_display": WORKFLOW_STAGE_LABELS.get(sale.workflow_stage, sale.workflow_stage),
        "delivery_date": sale.delivery_date.isoformat() if sale.delivery_date else None,
        "is_deleted": getattr(sale, "is_deleted", False),
    }
    if include_installments:
        data["installments"] = [
            installment_to_dict(i, user=user) for i in sale.installments.filter(is_deleted=False)
        ]
    if include_lines:
        data["line_items"] = [line_item_to_dict(i, user=user) for i in sale.line_items.all()]
    return data


def office_line_item_to_dict(item, user=None):
    from auth.org_roles import should_mask_amounts_for_user, should_mask_prices_for_user

    mask_prices = user and should_mask_prices_for_user(user)
    mask_amounts = user and should_mask_amounts_for_user(user)
    hide_money = mask_prices or mask_amounts
    return {
        "id": item.id,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "product_name": item.product_name,
        "product_model": item.product_model or "",
        "fabric": item.fabric or "",
        "color_name": item.color_name or "",
        "color_hex": item.color_hex or "",
        "quantity": item.quantity,
        "unit_price": None if hide_money else int(item.unit_price),
        "line_total": None if hide_money else int(item.line_total),
        "prices_masked": hide_money,
    }


def office_order_to_dict(order, include_installments=False, include_lines=False, user=None):
    from auth.org_roles import should_mask_amounts_for_user, should_mask_prices_for_user
    from auth.permissions import can_edit_sale
    from logic.branches import branch_labels
    from logic.sale_workflow import get_office_workflow_snapshot, workflow_progress_percent

    BRANCH_LABELS = branch_labels()
    mask_prices = user and should_mask_prices_for_user(user)
    mask_amounts = user and should_mask_amounts_for_user(user)
    hide_money = mask_prices or mask_amounts
    final = int(order.final_amount)
    paid = int(order.paid_amount)
    workflow = get_office_workflow_snapshot(order)

    data = {
        "id": order.id,
        "source_sale_id": order.source_sale_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer.full_name,
        "customer_phone": order.customer.phone if order.customer_id else "",
        "customer_address": order.customer.address or "",
        "amount": None if hide_money else int(order.amount),
        "discount_type": order.discount_type,
        "discount_value": None if hide_money else int(order.discount_value),
        "discount": None if hide_money else int(order.discount),
        "final_amount": None if hide_money else final,
        "paid_amount": None if hide_money else paid,
        "balance_due": None if hide_money else max(0, final - paid),
        "amounts_masked": hide_money,
        "invoice_number": order.invoice_number,
        "description": order.description,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "accounting_mode": order.accounting_mode,
        "accounting_mode_display": order.get_accounting_mode_display(),
        "order_kind": order.order_kind,
        "order_status": order.order_status,
        "status": order.status,
        "status_display": order.get_status_display(),
        "branch": order.branch or "",
        "branch_label": BRANCH_LABELS.get(order.branch, "—"),
        "seller_name": order.seller.full_name if order.seller_id else None,
        "recorded_by": order.recorded_by.username if order.recorded_by else None,
        "sold_at": order.sold_at.isoformat(),
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "workflow_stage": workflow["workflow_stage"],
        "workflow_stage_display": workflow["workflow_stage_display"],
        "workflow_progress": workflow_progress_percent(workflow["workflow_stage"]),
        "holder_department": workflow["holder_department"],
        "holder_name": workflow["holder_name"],
        "holder_detail": workflow["holder_detail"],
        "can_rollback": workflow["can_rollback"],
        "rollback_label": workflow["rollback_label"],
        "rollback_action": workflow["rollback_action"],
        "can_edit": bool(user and can_edit_sale(user, order.source_sale)),
        "created_at": order.created_at.isoformat(),
    }
    if include_installments:
        data["installments"] = [
            {
                "id": i.id,
                "amount": None if hide_money else int(i.amount),
                "due_date": i.due_date.isoformat(),
                "payment_method": i.payment_method,
                "check_number": i.check_number,
                "bank_name": i.bank_name,
                "status": i.status,
                "received_at": i.received_at.isoformat() if getattr(i, "received_at", None) else None,
                "receiver_name": getattr(i, "receiver_name", "") or "",
            }
            for i in order.installments.filter(is_deleted=False)
        ]
    from logic.check_accounting import sale_has_pending_checks

    data["has_pending_checks"] = sale_has_pending_checks(order.source_sale)
    lines = list(order.line_items.all())
    data["total_quantity"] = sum(int(i.quantity or 0) for i in lines)
    data["line_items_count"] = len(lines)
    if order.accounting_mode == "automatic":
        from logic.accounting_accounts import payment_account_label_for_sale

        data["payment_account_label"] = payment_account_label_for_sale(order.source_sale)
    else:
        data["payment_account_label"] = None
    if include_lines:
        data["line_items"] = [office_line_item_to_dict(i, user=user) for i in lines]
    return data


def factory_line_item_to_dict(item):
    return {
        "id": item.id,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "product_name": item.product_name,
        "product_model": item.product_model or "",
        "fabric": item.fabric or "",
        "color_name": item.color_name or "",
        "color_hex": item.color_hex or "",
        "quantity": item.quantity,
        "unit_price": None,
        "line_total": None,
        "prices_masked": True,
    }


def factory_order_to_dict(order, include_lines=False, user=None):
    from auth.org_roles import is_executive_user, is_freight_supervisor
    from auth.permissions import VIEW_FREIGHT_ORDERS, has_permission
    from logic.branches import branch_labels
    from logic.sale_workflow import WORKFLOW_STAGE_LABELS

    BRANCH_LABELS = branch_labels()
    show_customer = user and (
        is_executive_user(user)
        or is_freight_supervisor(user)
        or has_permission(user, VIEW_FREIGHT_ORDERS)
    )
    data = {
        "id": order.id,
        "source_sale_id": order.source_sale_id,
        "source_office_order_id": order.source_office_order_id,
        "customer_id": None,
        "customer_name": "—",
        "customer_phone": "",
        "customer_address": "",
        "customer_masked": True,
        "invoice_number": order.invoice_number,
        "description": order.description,
        "branch": order.branch or "",
        "branch_label": BRANCH_LABELS.get(order.branch, "—"),
        "order_kind": order.order_kind,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "workflow_stage": order.workflow_stage,
        "workflow_stage_display": WORKFLOW_STAGE_LABELS.get(order.workflow_stage, order.workflow_stage),
        "production_done_at": order.production_done_at.isoformat() if order.production_done_at else None,
        "amounts_masked": True,
        "final_amount": None,
        "created_at": order.created_at.isoformat(),
    }
    if show_customer and order.customer_id:
        customer = order.customer
        data.update(
            {
                "customer_id": customer.id,
                "customer_name": customer.full_name,
                "customer_phone": customer.phone or "",
                "customer_address": customer.address or "",
                "customer_masked": False,
            }
        )
    if include_lines:
        data["line_items"] = [factory_line_item_to_dict(i) for i in order.line_items.all()]
        from logic.materials import factory_order_materials_summary

        data.update(factory_order_materials_summary(order))
    return data


def installment_to_dict(inst, user=None):
    from auth.org_roles import should_mask_amounts_for_user, should_mask_prices_for_user

    hide_money = user and (should_mask_prices_for_user(user) or should_mask_amounts_for_user(user))
    reg = getattr(inst, "registration_account", None)
    dep = getattr(inst, "deposit_account", None)
    reg_label = ""
    dep_label = ""
    if reg:
        reg_label = f"{reg.code} — {reg.name}" if reg.code else reg.name
    if dep:
        dep_label = f"{dep.code} — {dep.name}" if dep.code else dep.name
    return {
        "id": inst.id,
        "sale_id": inst.sale_id,
        "customer_name": inst.sale.customer.full_name if inst.sale_id else "",
        "amount": None if hide_money else int(inst.amount),
        "due_date": inst.due_date.isoformat(),
        "payment_method": inst.payment_method,
        "payment_method_display": inst.get_payment_method_display(),
        "check_number": inst.check_number,
        "bank_name": inst.bank_name,
        "received_at": inst.received_at.isoformat() if getattr(inst, "received_at", None) else None,
        "receiver_name": getattr(inst, "receiver_name", "") or "",
        "status": inst.status,
        "status_display": inst.get_status_display(),
        "paid_at": inst.paid_at.isoformat() if inst.paid_at else None,
        "notes": inst.notes,
        "accounting_registered_at": (
            inst.accounting_registered_at.isoformat()
            if getattr(inst, "accounting_registered_at", None)
            else None
        ),
        "registration_account_id": reg.id if reg else None,
        "registration_account_label": reg_label,
        "deposit_account_id": dep.id if dep else None,
        "deposit_account_label": dep_label,
        "is_deleted": getattr(inst, "is_deleted", False),
    }


def checks_report_to_dict(report):
    return {
        "year": report["year"],
        "month": report["month"],
        "count": report["count"],
        "total_amount": report["total_amount"],
        "paid_amount": report["paid_amount"],
        "pending_amount": report["pending_amount"],
        "results": [installment_to_dict(i) for i in report["results"]],
    }


def attendance_to_dict(record):
    from logic.attendance import attendance_to_dict as _attendance_to_dict

    return _attendance_to_dict(record)


def accounting_to_dict(entry, user=None, *, ledger=None):
    from auth.permissions import TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE, has_permission
    from logic.accounting import entry_permissions, is_system_entry, resolve_entry_accounts
    from logic.accounting_transfer import is_factory_entry_transferred
    from logic.ledger import FACTORY_LEDGER, OFFICE_LEDGER

    ledger = ledger or OFFICE_LEDGER
    sale = entry.sale if getattr(entry, "sale_id", None) else None
    factory_order = entry.factory_order if getattr(entry, "factory_order_id", None) else None
    is_system = is_system_entry(entry, ledger=ledger)
    perms = entry_permissions(entry, user=user, ledger=ledger)
    account = entry.account if getattr(entry, "account_id", None) else None
    general, subsidiary, detailed = resolve_entry_accounts(
        account,
        general=entry.general_account,
        subsidiary=entry.subsidiary_account,
        detailed=entry.detailed_account,
    )
    subsidiary_ref = entry.subsidiary if getattr(entry, "subsidiary_id", None) else None
    detailed_ref = entry.detailed if getattr(entry, "detailed_id", None) else None
    transferred_at = getattr(entry, "transferred_to_office_at", None)
    office_doc_code = getattr(entry, "office_document_code", "") or ""
    can_transfer = (
        ledger.id == "factory"
        and user
        and has_permission(user, TRANSFER_FACTORY_ACCOUNTING_TO_OFFICE)
        and not is_factory_entry_transferred(entry)
    )
    return {
        "id": entry.id,
        "entry_type": entry.entry_type,
        "entry_type_display": entry.get_entry_type_display(),
        "account_id": account.id if account else None,
        "account_code": account.code if account else "",
        "account_slug": account.slug if account else None,
        "account_name": account.name if account else entry.get_entry_type_display(),
        "account_class": account.account_class if account else None,
        "account_class_label": account.get_account_class_display() if account else None,
        "subsidiary_id": subsidiary_ref.id if subsidiary_ref else None,
        "subsidiary_code": subsidiary_ref.full_code if subsidiary_ref else "",
        "detailed_id": detailed_ref.id if detailed_ref else None,
        "detailed_code": detailed_ref.full_code if detailed_ref else "",
        "document_code": entry.document_code or "",
        "document_number": entry.document_number,
        "attach_code": entry.attach_code or "",
        "general_account": general,
        "subsidiary_account": subsidiary,
        "detailed_account": detailed,
        "opening_debit": int(entry.opening_debit),
        "opening_credit": int(entry.opening_credit),
        "turnover_debit": int(entry.debit),
        "turnover_credit": int(entry.credit),
        "balance_debit": int(entry.balance_debit),
        "balance_credit": int(entry.balance_credit),
        "debit": int(entry.debit),
        "credit": int(entry.credit),
        "amount": int(entry.amount),
        "entry_date": entry.entry_date.isoformat(),
        "description": entry.description,
        "sale_id": getattr(entry, "sale_id", None),
        "factory_order_id": getattr(entry, "factory_order_id", None),
        "invoice_number": (
            sale.invoice_number if sale else (factory_order.invoice_number if factory_order else "")
        ),
        "customer_name": sale.customer.full_name if sale else "",
        "is_approved": entry.is_approved,
        "is_system": is_system,
        "can_edit": perms["can_edit"],
        "can_delete": perms["can_delete"],
        "edit_mode": perms["edit_mode"],
        "transferred_to_office_at": transferred_at.isoformat() if transferred_at else None,
        "office_document_code": office_doc_code,
        "can_transfer": can_transfer,
        "created_at": entry.created_at.isoformat(),
    }


def level_history_to_dict(item):
    return {
        "id": item.id,
        "customer_id": item.customer_id,
        "previous_level": item.previous_level.name if item.previous_level else None,
        "new_level": item.new_level.name if item.new_level else None,
        "reason": item.reason,
        "total_purchases_at_change": int(item.total_purchases_at_change),
        "changed_at": item.changed_at.isoformat(),
    }


def sms_to_dict(log):
    return {
        "id": log.id,
        "customer_id": log.customer_id,
        "phone_number": log.phone_number,
        "message": log.message,
        "status": log.status,
        "status_display": log.get_status_display(),
        "sms_type": log.sms_type,
        "sms_type_display": log.get_sms_type_display(),
        "provider_response": log.provider_response,
        "error_message": log.error_message,
        "created_at": log.created_at.isoformat(),
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        "created_by": log.created_by.username if log.created_by else None,
    }


def sms_result_to_dict(result):
    return {
        "successful": result["successful"],
        "failed": result["failed"],
        "skipped": result["skipped"],
        "results": [sms_to_dict(log) for log in result["results"]],
    }
