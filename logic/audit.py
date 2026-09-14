"""ثبت و فهرست لاگ فعالیت‌ها."""

from django.db import transaction
from django.db.models import Q

from backend.models import AuditEntityType, AuditLog


TARGET_RELATIONS = {
    "Sale": ("AuditOrderTarget", "order_target"),
    "OfficeOrder": ("AuditOfficeOrderTarget", "office_order_target"),
    "FactoryOrder": ("AuditFactoryOrderTarget", "factory_order_target"),
    "Customer": ("AuditCustomerTarget", "customer_target"),
    "JournalEntry": ("AuditJournalTarget", "journal_target"),
    "Material": ("AuditMaterialTarget", "material_target"),
    "Product": ("AuditProductTarget", "product_target"),
    "ProductCategory": ("AuditProductCategoryTarget", "product_category_target"),
    "Seller": ("AuditSellerTarget", "seller_target"),
    "StaffAttendance": ("AuditAttendanceTarget", "attendance_target"),
    "SaleInstallment": ("AuditInstallmentTarget", "installment_target"),
    "LoyaltyLevel": ("AuditLoyaltyLevelTarget", "loyalty_level_target"),
    "ReminderCampaign": ("AuditReminderCampaignTarget", "reminder_campaign_target"),
    "RoleDefinition": ("AuditRoleDefinitionTarget", "role_definition_target"),
    "User": ("AuditUserTarget", "subject_user_target"),
}


def log_action(
    user,
    action,
    message,
    *,
    entity_type="",
    entity_id="",
    details=None,
    is_executive_only=False,
):
    from backend import models as backend_models

    entity_type = (entity_type or "").strip()
    if entity_type and entity_type not in TARGET_RELATIONS:
        raise ValueError(f"Unsupported audit entity type: {entity_type}")

    with transaction.atomic():
        if entity_type:
            AuditEntityType.objects.get_or_create(
                code=entity_type, defaults={"label": entity_type}
            )
        event = AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            entity_type_ref_id=entity_type or None,
            message=message,
            details=details or {},
            is_executive_only=is_executive_only,
        )
        if entity_type and entity_id not in ("", None):
            target_model_name, _ = TARGET_RELATIONS[entity_type]
            target_model = getattr(backend_models, target_model_name)
            target_model.objects.create(event=event, target_id=entity_id)
        return event


def audit_log_to_dict(entry):
    user = entry.user
    return {
        "id": entry.id,
        "user_name": (user.get_full_name() or user.username) if user else "—",
        "username": user.username if user else "",
        "action": entry.action,
        "action_display": entry.get_action_display(),
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "message": entry.message,
        "details": entry.details,
        "is_executive_only": entry.is_executive_only,
        "created_at": entry.created_at.isoformat(),
    }


def list_audit_logs(params, *, include_executive=False):
    relations = [relation for _, relation in TARGET_RELATIONS.values()]
    qs = AuditLog.objects.select_related("user", "entity_type_ref", *relations).all()
    if not include_executive:
        qs = qs.filter(is_executive_only=False)

    action = (params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    entity_types = [
        {"value": code, "label": code}
        for code in qs.exclude(entity_type_ref__isnull=True)
        .values_list("entity_type_ref_id", flat=True)
        .distinct()
        .order_by("entity_type_ref_id")
    ]

    entity_type = (params.get("entity_type") or "").strip()
    if entity_type:
        qs = qs.filter(entity_type_ref_id=entity_type)

    search = (params.get("search") or "").strip()
    if search:
        query = (
            Q(message__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
        matching_types = [
            entity_type
            for entity_type in TARGET_RELATIONS
            if search.casefold() in entity_type.casefold()
        ]
        if matching_types:
            query |= Q(entity_type_ref_id__in=matching_types)
        qs = qs.filter(query)

    from logic.pagination import paginate

    page, meta = paginate(qs, params)
    return {
        "results": [audit_log_to_dict(e) for e in page],
        **meta,
        "actions": [
            {"value": value, "label": label}
            for value, label in AuditLog.ACTION_CHOICES
        ],
        "entity_types": entity_types,
    }
