"""چرخه ماژولار سفارش — پیکربندی اسلات‌ها، انبار و دسترسی نظارت."""

from django.contrib.auth import get_user_model
from django.db.models import Q

from auth.org_roles import is_executive_user
from auth.permissions import (
    APPROVE_SALE_ACCOUNTING,
    APPROVE_SALE_BRANCH,
    CREATE_SALE,
    MANAGE_FACTORY_ORDERS,
    MANAGE_PICKUP_ORDERS,
    MANAGE_WAREHOUSE_ORDERS,
    VIEW_CYCLE_WATCH,
    VIEW_FACTORY_ORDERS,
    VIEW_PICKUP_ORDERS,
    VIEW_WAREHOUSE_ORDERS,
    has_full_access,
    has_permission,
    is_system_admin,
)
from backend.models import Branch, CycleSlot, OrderCycle, Sale, StaffProfile, Warehouse, WorkflowStage
from logic.sellers import get_user_branch

User = get_user_model()

STEP_BRANCH_SUPERVISOR = "branch_supervisor"
STEP_SHOP_CRM_MONITOR = "shop_crm_monitor"
STEP_CRM = "crm"
STEP_FACTORY = "factory"
STEP_WAREHOUSE = "warehouse"
STEP_PICKUP = "customer_pickup"
STEP_MERCHANT = "merchant"
STEP_FULFILLMENT_SUPERVISOR = "fulfillment_supervisor"

ROUTE_FACTORY = Sale.FULFILLMENT_ROUTE_FACTORY
ROUTE_WAREHOUSE = Sale.FULFILLMENT_ROUTE_WAREHOUSE
ROUTE_PICKUP = Sale.FULFILLMENT_ROUTE_PICKUP
ROUTE_MERCHANT = Sale.FULFILLMENT_ROUTE_MERCHANT

ROUTE_STEPS = {
    ROUTE_FACTORY: STEP_FACTORY,
    ROUTE_WAREHOUSE: STEP_WAREHOUSE,
    ROUTE_PICKUP: STEP_PICKUP,
    ROUTE_MERCHANT: STEP_MERCHANT,
}

ROUTE_STAGES = {
    ROUTE_FACTORY: Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
    ROUTE_WAREHOUSE: Sale.WORKFLOW_STAGE_IN_WAREHOUSE,
    ROUTE_PICKUP: Sale.WORKFLOW_STAGE_READY_FOR_PICKUP,
    ROUTE_MERCHANT: Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
}

ROUTE_LABELS = {
    ROUTE_FACTORY: "کارخانه",
    ROUTE_WAREHOUSE: "انبار",
    ROUTE_PICKUP: "تحویل به مشتری",
    ROUTE_MERCHANT: "بازرگان",
}

SLOT_SPECS = [
    {
        "step_key": STEP_BRANCH_SUPERVISOR,
        "label": "سرپرست شعبه",
        "kind": CycleSlot.KIND_FIXED,
        "is_enabled": True,
        "sort_order": 1,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_SHOP_CRM_MONITOR,
        "label": "ناظر فروشگاه و CRM",
        "kind": CycleSlot.KIND_MONITOR,
        "is_enabled": True,
        "sort_order": 2,
        "requires_assignee": True,
    },
    {
        "step_key": STEP_CRM,
        "label": "اداری CRM",
        "kind": CycleSlot.KIND_FIXED,
        "is_enabled": True,
        "sort_order": 3,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_FACTORY,
        "label": "کارخانه",
        "kind": CycleSlot.KIND_ROUTE,
        "is_enabled": True,
        "sort_order": 10,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_WAREHOUSE,
        "label": "انبار",
        "kind": CycleSlot.KIND_ROUTE,
        "is_enabled": True,
        "sort_order": 11,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_PICKUP,
        "label": "تحویل به مشتری",
        "kind": CycleSlot.KIND_ROUTE,
        "is_enabled": True,
        "sort_order": 12,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_MERCHANT,
        "label": "بازرگان",
        "kind": CycleSlot.KIND_ROUTE,
        "is_enabled": True,
        "sort_order": 13,
        "requires_assignee": False,
    },
    {
        "step_key": STEP_FULFILLMENT_SUPERVISOR,
        "label": "ناظر همه مسیرها",
        "kind": CycleSlot.KIND_MONITOR,
        "is_enabled": True,
        "sort_order": 20,
        "requires_assignee": True,
    },
]

REQUIRED_MONITOR_STEPS = {STEP_SHOP_CRM_MONITOR, STEP_FULFILLMENT_SUPERVISOR}

SHOP_CRM_WATCH_STAGES = {
    Sale.WORKFLOW_STAGE_PENDING_BRANCH,
    Sale.WORKFLOW_STAGE_BRANCH_APPROVED,
}

FULFILLMENT_WATCH_STAGES = {
    Sale.WORKFLOW_STAGE_ACCOUNTING_APPROVED,
    Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED,
    Sale.WORKFLOW_STAGE_IN_PRODUCTION,
    Sale.WORKFLOW_STAGE_PRODUCTION_DONE,
    Sale.WORKFLOW_STAGE_IN_FREIGHT,
    Sale.WORKFLOW_STAGE_IN_WAREHOUSE,
    Sale.WORKFLOW_STAGE_READY_FOR_PICKUP,
    Sale.WORKFLOW_STAGE_COMPLETED,
}

NEW_WORKFLOW_STAGES = [
    (Sale.WORKFLOW_STAGE_IN_WAREHOUSE, "در انبار", 7, False),
    (Sale.WORKFLOW_STAGE_READY_FOR_PICKUP, "آماده تحویل حضوری", 8, False),
    (Sale.WORKFLOW_STAGE_MERCHANT_ASSIGNED, "بازرگان — صف کارخانه", 9, False),
]

SLOT_PERMISSIONS = {
    STEP_WAREHOUSE: (VIEW_WAREHOUSE_ORDERS, MANAGE_WAREHOUSE_ORDERS),
    STEP_PICKUP: (VIEW_PICKUP_ORDERS, MANAGE_PICKUP_ORDERS),
    STEP_FACTORY: (VIEW_FACTORY_ORDERS, MANAGE_FACTORY_ORDERS),
    STEP_MERCHANT: (VIEW_FACTORY_ORDERS, MANAGE_FACTORY_ORDERS),
    STEP_SHOP_CRM_MONITOR: (VIEW_CYCLE_WATCH,),
    STEP_FULFILLMENT_SUPERVISOR: (VIEW_CYCLE_WATCH,),
}


def seed_workflow_stages():
    for code, label, sort_order, is_terminal in NEW_WORKFLOW_STAGES:
        WorkflowStage.objects.update_or_create(
            code=code,
            defaults={
                "label": label,
                "sort_order": sort_order,
                "is_terminal": is_terminal,
                "is_active": True,
            },
        )
    WorkflowStage.objects.filter(code=Sale.WORKFLOW_STAGE_COMPLETED).update(sort_order=10)


def seed_order_cycle():
    seed_workflow_stages()
    cycle = OrderCycle.objects.filter(is_active=True).first()
    if cycle is None:
        cycle = OrderCycle.objects.create(name="چرخه فروش", is_active=True)
    for spec in SLOT_SPECS:
        CycleSlot.objects.update_or_create(
            cycle=cycle,
            step_key=spec["step_key"],
            defaults={
                "label": spec["label"],
                "kind": spec["kind"],
                "is_enabled": spec["is_enabled"],
                "sort_order": spec["sort_order"],
            },
        )
    return cycle


def get_active_cycle():
    cycle = OrderCycle.objects.filter(is_active=True).prefetch_related(
        "slots", "slots__user", "slots__org_rank"
    ).first()
    if cycle is None:
        return seed_order_cycle()
    if cycle.slots.count() < len(SLOT_SPECS):
        return seed_order_cycle()
    return cycle


def _user_display(user):
    if not user:
        return None
    name = user.get_full_name() or user.username
    return name.strip() or user.username


def slot_to_dict(slot):
    return {
        "id": slot.id,
        "step_key": slot.step_key,
        "label": slot.label,
        "kind": slot.kind,
        "assignee_type": slot.assignee_type or "",
        "user_id": slot.user_id,
        "user_name": _user_display(slot.user),
        "org_rank_id": slot.org_rank_id,
        "org_rank_name": slot.org_rank.name if slot.org_rank_id else None,
        "is_enabled": slot.is_enabled,
        "sort_order": slot.sort_order,
        "requires_assignee": slot.step_key in REQUIRED_MONITOR_STEPS,
    }


def warehouse_to_dict(warehouse):
    return {
        "id": warehouse.id,
        "code": warehouse.code,
        "label": warehouse.label,
        "branch": warehouse.branch_id or "",
        "branch_label": warehouse.branch.label if warehouse.branch_id else "",
        "sort_order": warehouse.sort_order,
        "is_active": warehouse.is_active,
    }


def cycle_to_dict(cycle=None):
    cycle = cycle or get_active_cycle()
    slots = {slot.step_key: slot_to_dict(slot) for slot in cycle.slots.all()}
    return {
        "id": cycle.id,
        "name": cycle.name,
        "is_active": cycle.is_active,
        "slots": [slots.get(spec["step_key"]) or {**spec, "assignee_type": "", "user_id": None, "org_rank_id": None} for spec in SLOT_SPECS],
        "enabled_routes": enabled_routes(cycle),
        "warehouses": [warehouse_to_dict(w) for w in list_warehouses(active_only=False)],
    }


def enabled_routes(cycle=None):
    cycle = cycle or get_active_cycle()
    routes = []
    by_key = {slot.step_key: slot for slot in cycle.slots.all()}
    for route, step_key in ROUTE_STEPS.items():
        slot = by_key.get(step_key)
        if slot is None or slot.is_enabled:
            routes.append(route)
    return routes


def _slot_has_assignee(slot):
    if not slot:
        return False
    if slot.assignee_type == CycleSlot.ASSIGNEE_USER:
        return bool(slot.user_id)
    if slot.assignee_type == CycleSlot.ASSIGNEE_RANK:
        return bool(slot.org_rank_id)
    return bool(slot.user_id or slot.org_rank_id)


def validate_cycle_payload(data, cycle):
    slots_payload = data.get("slots")
    if not isinstance(slots_payload, list):
        raise ValueError("فهرست اسلات‌های چرخه نامعتبر است.")
    by_key = {item.get("step_key"): item for item in slots_payload if item.get("step_key")}
    for spec in SLOT_SPECS:
        item = by_key.get(spec["step_key"], {})
        assignee_type = (item.get("assignee_type") or "").strip()
        user_id = item.get("user_id") or None
        org_rank_id = item.get("org_rank_id") or None
        if spec["step_key"] in REQUIRED_MONITOR_STEPS:
            if assignee_type == CycleSlot.ASSIGNEE_USER and not user_id:
                raise ValueError(f"برای «{spec['label']}» انتخاب کاربر الزامی است.")
            if assignee_type == CycleSlot.ASSIGNEE_RANK and not org_rank_id:
                raise ValueError(f"برای «{spec['label']}» انتخاب مقام الزامی است.")
            if assignee_type not in {CycleSlot.ASSIGNEE_USER, CycleSlot.ASSIGNEE_RANK}:
                raise ValueError(f"برای «{spec['label']}» باید مقام یا کاربر انتخاب شود.")
        if assignee_type == CycleSlot.ASSIGNEE_USER and org_rank_id:
            org_rank_id = None
        if assignee_type == CycleSlot.ASSIGNEE_RANK and user_id:
            user_id = None
        if assignee_type == CycleSlot.ASSIGNEE_USER and user_id and not User.objects.filter(pk=user_id, is_active=True).exists():
            raise ValueError(f"کاربر انتخاب‌شده برای «{spec['label']}» معتبر نیست.")
        if assignee_type == CycleSlot.ASSIGNEE_RANK and org_rank_id and not True:
            pass
    enabled = []
    for route, step_key in ROUTE_STEPS.items():
        item = by_key.get(step_key)
        is_enabled = True if item is None else bool(item.get("is_enabled", True))
        if item is None:
            existing = cycle.slots.filter(step_key=step_key).first()
            is_enabled = existing.is_enabled if existing else True
        if is_enabled:
            enabled.append(route)
    if not enabled:
        raise ValueError("حداقل یکی از مسیرهای بعد از CRM باید روشن باشد.")
    return by_key


def save_cycle(data):
    from backend.models import OrgRank

    cycle = get_active_cycle()
    by_key = validate_cycle_payload(data, cycle)
    if data.get("name"):
        cycle.name = str(data.get("name")).strip()[:80] or cycle.name
        cycle.save(update_fields=["name", "updated_at"])
    for spec in SLOT_SPECS:
        item = by_key.get(spec["step_key"], {})
        assignee_type = (item.get("assignee_type") or "").strip()
        user_id = item.get("user_id") or None
        org_rank_id = item.get("org_rank_id") or None
        if assignee_type == CycleSlot.ASSIGNEE_USER:
            org_rank_id = None
        elif assignee_type == CycleSlot.ASSIGNEE_RANK:
            user_id = None
            if org_rank_id and not OrgRank.objects.filter(pk=org_rank_id).exists():
                raise ValueError(f"مقام انتخاب‌شده برای «{spec['label']}» معتبر نیست.")
        else:
            user_id = None
            org_rank_id = None
            assignee_type = ""
        is_enabled = bool(item.get("is_enabled", spec["is_enabled"]))
        if spec["kind"] != CycleSlot.KIND_ROUTE:
            is_enabled = True
        CycleSlot.objects.update_or_create(
            cycle=cycle,
            step_key=spec["step_key"],
            defaults={
                "label": spec["label"],
                "kind": spec["kind"],
                "sort_order": spec["sort_order"],
                "assignee_type": assignee_type,
                "user_id": user_id,
                "org_rank_id": org_rank_id,
                "is_enabled": is_enabled,
            },
        )
    return get_active_cycle()


def list_warehouses(*, active_only=True):
    qs = Warehouse.objects.select_related("branch").order_by("sort_order", "label")
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


def create_warehouse(data):
    code = (data.get("code") or "").strip()
    label = (data.get("label") or "").strip()
    if not code or not label:
        raise ValueError("کد و نام انبار الزامی است.")
    if Warehouse.objects.filter(code=code).exists():
        raise ValueError("این کد انبار تکراری است.")
    branch_id = (data.get("branch") or "").strip() or None
    if branch_id and not Branch.objects.filter(code=branch_id).exists():
        raise ValueError("شعبه انتخاب‌شده معتبر نیست.")
    return Warehouse.objects.create(
        code=code,
        label=label,
        branch_id=branch_id,
        sort_order=int(data.get("sort_order") or 0),
        is_active=bool(data.get("is_active", True)),
    )


def update_warehouse(warehouse, data):
    if "label" in data:
        label = (data.get("label") or "").strip()
        if not label:
            raise ValueError("نام انبار الزامی است.")
        warehouse.label = label
    if "code" in data:
        code = (data.get("code") or "").strip()
        if not code:
            raise ValueError("کد انبار الزامی است.")
        if Warehouse.objects.exclude(pk=warehouse.pk).filter(code=code).exists():
            raise ValueError("این کد انبار تکراری است.")
        warehouse.code = code
    if "branch" in data:
        branch_id = (data.get("branch") or "").strip() or None
        if branch_id and not Branch.objects.filter(code=branch_id).exists():
            raise ValueError("شعبه انتخاب‌شده معتبر نیست.")
        warehouse.branch_id = branch_id
    if "sort_order" in data:
        warehouse.sort_order = int(data.get("sort_order") or 0)
    if "is_active" in data:
        warehouse.is_active = bool(data.get("is_active"))
    warehouse.save()
    return warehouse


def get_user_org_rank_id(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.staff_profile.org_rank_id
    except StaffProfile.DoesNotExist:
        return None


def user_matches_slot(user, slot):
    if not user or not slot:
        return False
    if slot.assignee_type == CycleSlot.ASSIGNEE_USER:
        return slot.user_id == user.id
    if slot.assignee_type == CycleSlot.ASSIGNEE_RANK:
        return bool(slot.org_rank_id) and get_user_org_rank_id(user) == slot.org_rank_id
    if slot.user_id == user.id:
        return True
    if slot.org_rank_id and get_user_org_rank_id(user) == slot.org_rank_id:
        return True
    return False


def cycle_flags_for_user(user):
    cycle = get_active_cycle()
    by_key = {slot.step_key: slot for slot in cycle.slots.all()}
    is_shop_crm_monitor = user_matches_slot(user, by_key.get(STEP_SHOP_CRM_MONITOR))
    is_fulfillment_supervisor = user_matches_slot(user, by_key.get(STEP_FULFILLMENT_SUPERVISOR))
    return {
        "is_shop_crm_monitor": is_shop_crm_monitor,
        "is_fulfillment_supervisor": is_fulfillment_supervisor,
        "can_watch_cycle": is_shop_crm_monitor or is_fulfillment_supervisor or is_system_admin(user) or is_executive_user(user),
        "can_manage_warehouse": user_matches_slot(user, by_key.get(STEP_WAREHOUSE)),
        "can_manage_pickup": user_matches_slot(user, by_key.get(STEP_PICKUP)),
        "enabled_routes": enabled_routes(cycle),
    }


def extra_permissions_from_cycle(user):
    flags = cycle_flags_for_user(user)
    extra = set()
    if flags["is_shop_crm_monitor"] or flags["is_fulfillment_supervisor"]:
        extra.add(VIEW_CYCLE_WATCH)
    if flags["can_manage_warehouse"]:
        extra.update({VIEW_WAREHOUSE_ORDERS, MANAGE_WAREHOUSE_ORDERS})
    if flags["can_manage_pickup"]:
        extra.update({VIEW_PICKUP_ORDERS, MANAGE_PICKUP_ORDERS})
    if flags["is_fulfillment_supervisor"]:
        extra.update(
            {
                VIEW_WAREHOUSE_ORDERS,
                VIEW_PICKUP_ORDERS,
                VIEW_FACTORY_ORDERS,
            }
        )
    return extra


def can_act_on_step(user, step_key, manage=False):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_system_admin(user) or has_full_access(user) or is_executive_user(user):
        return True
    cycle = get_active_cycle()
    slot = next((s for s in cycle.slots.all() if s.step_key == step_key), None)
    if user_matches_slot(user, slot):
        return True
    perms = SLOT_PERMISSIONS.get(step_key, ())
    if manage:
        manage_codes = [p for p in perms if p.startswith("manage_")]
        return any(has_permission(user, code) for code in manage_codes) if manage_codes else any(
            has_permission(user, code) for code in perms
        )
    return any(has_permission(user, code) for code in perms)


def can_complete_warehouse(user, sale=None):
    if can_act_on_step(user, STEP_WAREHOUSE, manage=True):
        return True
    return has_permission(user, APPROVE_SALE_ACCOUNTING) or has_permission(user, MANAGE_WAREHOUSE_ORDERS)


def can_complete_pickup(user, sale=None):
    if can_act_on_step(user, STEP_PICKUP, manage=True):
        return True
    if has_permission(user, MANAGE_PICKUP_ORDERS):
        return True
    if sale is None:
        return has_permission(user, CREATE_SALE) or has_permission(user, APPROVE_SALE_BRANCH)
    user_branch = get_user_branch(user)
    if user_branch and sale.branch_id == user_branch:
        return has_permission(user, CREATE_SALE) or has_permission(user, APPROVE_SALE_BRANCH)
    return False


def can_list_warehouse_orders(user):
    return can_complete_warehouse(user) or has_permission(user, VIEW_WAREHOUSE_ORDERS) or cycle_flags_for_user(user)["is_fulfillment_supervisor"]


def can_list_pickup_orders(user):
    return can_complete_pickup(user) or has_permission(user, VIEW_PICKUP_ORDERS) or cycle_flags_for_user(user)["is_fulfillment_supervisor"]


def resolve_fulfillment_route(route):
    value = (route or "").strip() or ROUTE_FACTORY
    if value not in ROUTE_STAGES:
        raise ValueError("مسیر ارسال نامعتبر است.")
    if value not in enabled_routes():
        raise ValueError("این مسیر ارسال در چرخه خاموش است.")
    return value


def apply_fulfillment_fields(sale, *, route, warehouse_id=None, source_branch=None, merchant_user_id=None):
    route = resolve_fulfillment_route(route)
    warehouse = None
    source = None
    merchant = None
    if route == ROUTE_WAREHOUSE:
        has_warehouse = bool(warehouse_id)
        has_branch = bool(source_branch)
        if has_warehouse == has_branch:
            raise ValueError("برای مسیر انبار باید دقیقاً یکی از انبار یا شعبه را انتخاب کنید.")
        if has_warehouse:
            warehouse = Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
            if warehouse is None:
                raise ValueError("انبار انتخاب‌شده معتبر نیست.")
        else:
            source = Branch.objects.filter(code=str(source_branch).strip(), is_active=True).first()
            if source is None:
                raise ValueError("شعبه مبدأ معتبر نیست.")
    elif route == ROUTE_MERCHANT:
        if not merchant_user_id:
            raise ValueError("برای مسیر بازرگان انتخاب همکار الزامی است.")
        merchant = User.objects.filter(pk=merchant_user_id, is_active=True).first()
        if merchant is None:
            raise ValueError("همکار انتخاب‌شده معتبر نیست.")
    return {
        "fulfillment_route": route,
        "fulfillment_warehouse": warehouse,
        "fulfillment_source_branch": source,
        "merchant_user": merchant,
        "workflow_stage_id": ROUTE_STAGES[route],
    }


def fulfillment_note(route, *, warehouse=None, source_branch=None, merchant=None):
    if route == ROUTE_WAREHOUSE:
        if warehouse:
            return f"تایید اداری — ارسال به انبار {warehouse.label}"
        if source_branch:
            return f"تایید اداری — ارسال از شعبه {source_branch.label}"
        return "تایید اداری — انبار"
    if route == ROUTE_PICKUP:
        return "تایید اداری — تحویل حضوری به مشتری"
    if route == ROUTE_MERCHANT:
        name = _user_display(merchant) or "همکار"
        return f"تایید اداری — بازرگان ({name})"
    return "تایید اداری — ارسال به کارخانه"


def sale_fulfillment_payload(sale):
    warehouse = sale.fulfillment_warehouse
    source = sale.fulfillment_source_branch
    merchant = sale.merchant_user
    return {
        "fulfillment_route": sale.fulfillment_route or "",
        "fulfillment_route_display": ROUTE_LABELS.get(sale.fulfillment_route or "", ""),
        "fulfillment_warehouse_id": sale.fulfillment_warehouse_id,
        "fulfillment_warehouse_label": warehouse.label if warehouse else "",
        "fulfillment_source_branch": sale.fulfillment_source_branch_id or "",
        "fulfillment_source_branch_label": source.label if source else "",
        "merchant_user_id": sale.merchant_user_id,
        "merchant_user_name": _user_display(merchant) or "",
    }


def watch_queryset(user, scope="shop_crm"):
    from backend.models import Sale as SaleModel

    qs = SaleModel.objects.filter(is_deleted=False).select_related(
        "customer",
        "seller",
        "recorded_by",
        "fulfillment_warehouse",
        "fulfillment_source_branch",
        "merchant_user",
        "branch",
    )
    flags = cycle_flags_for_user(user)
    if scope == "fulfillment":
        if not (flags["is_fulfillment_supervisor"] or is_system_admin(user) or is_executive_user(user) or has_permission(user, VIEW_CYCLE_WATCH)):
            return qs.none()
        return qs.filter(workflow_stage_id__in=FULFILLMENT_WATCH_STAGES).order_by("-sold_at")
    if not (flags["is_shop_crm_monitor"] or is_system_admin(user) or is_executive_user(user) or has_permission(user, VIEW_CYCLE_WATCH)):
        return qs.none()
    return qs.filter(workflow_stage_id__in=SHOP_CRM_WATCH_STAGES).order_by("-sold_at")


def warehouse_order_queryset(user):
    qs = Sale.objects.filter(
        is_deleted=False,
        workflow_stage_id=Sale.WORKFLOW_STAGE_IN_WAREHOUSE,
    ).select_related(
        "customer",
        "seller",
        "fulfillment_warehouse",
        "fulfillment_source_branch",
        "branch",
    )
    if not can_list_warehouse_orders(user):
        return qs.none()
    return qs.order_by("-sold_at")


def pickup_order_queryset(user):
    qs = Sale.objects.filter(
        is_deleted=False,
        workflow_stage_id=Sale.WORKFLOW_STAGE_READY_FOR_PICKUP,
    ).select_related("customer", "seller", "branch")
    if not can_list_pickup_orders(user):
        return qs.none()
    if is_system_admin(user) or has_full_access(user) or is_executive_user(user):
        return qs.order_by("-sold_at")
    if can_act_on_step(user, STEP_PICKUP) or has_permission(user, VIEW_PICKUP_ORDERS):
        branch = get_user_branch(user)
        if branch:
            qs = qs.filter(Q(branch_id=branch) | Q(fulfillment_source_branch_id=branch))
        return qs.order_by("-sold_at")
    branch = get_user_branch(user)
    if branch:
        return qs.filter(branch_id=branch).order_by("-sold_at")
    return qs.none()
