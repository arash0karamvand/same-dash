"""API endpoints برای مدیریت فعالیت‌ها و وظایف."""

from datetime import datetime
from django.db.models import Q
from django.utils import timezone

from api.helpers import api_view, success, fail, parse_json
from backend.models import Activity, Task, Customer, Sale


@api_view(["GET", "POST"])
def activities_list(request):
    """
    GET: لیست فعالیت‌ها با فیلتر
    POST: ثبت فعالیت جدید
    """
    if request.method == "GET":
        # Filters
        user_id = request.GET.get("user")
        customer_id = request.GET.get("customer")
        activity_type = request.GET.get("type")
        date_range = request.GET.get("date_range", "week")  # week, month, all
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 50))

        qs = Activity.objects.select_related("user", "customer", "sale", "task").all()

        if user_id:
            qs = qs.filter(user_id=user_id)
        else:
            # Default: activities of current user
            qs = qs.filter(user=request.user)

        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        if activity_type and activity_type != "all":
            qs = qs.filter(activity_type=activity_type)

        # Date range filter
        if date_range == "week":
            start_date = timezone.now() - timezone.timedelta(days=7)
            qs = qs.filter(occurred_at__gte=start_date)
        elif date_range == "month":
            start_date = timezone.now() - timezone.timedelta(days=30)
            qs = qs.filter(occurred_at__gte=start_date)

        total = qs.count()
        activities = qs[offset : offset + limit]

        results = [
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "activity_type_display": activity.get_activity_type_display(),
                "title": activity.title,
                "description": activity.description,
                "user_name": activity.user.get_full_name() or activity.user.username,
                "customer_id": activity.customer_id,
                "customer_name": activity.customer.name if activity.customer else None,
                "sale_id": activity.sale_id,
                "sale_code": activity.sale.sale_code if activity.sale else None,
                "task_id": activity.task_id,
                "metadata": activity.metadata,
                "occurred_at": activity.occurred_at.isoformat(),
                "created_at": activity.created_at.isoformat(),
            }
            for activity in activities
        ]

        return JsonResponse({"ok": True, "data": {"results": results, "total": total}})

    # POST: create new activity
    data = parse_json(request)
    activity = Activity.objects.create(
        activity_type=data["activity_type"],
        title=data["title"],
        description=data.get("description", ""),
        user=request.user,
        customer_id=data.get("customer_id"),
        sale_id=data.get("sale_id"),
        task_id=data.get("task_id"),
        metadata=data.get("metadata", {}),
        occurred_at=data.get("occurred_at") or timezone.now(),
    )

    return success(
        {
            "id": activity.id,
            "activity_type": activity.activity_type,
            "title": activity.title,
            "occurred_at": activity.occurred_at.isoformat(),
        }
    )


@api_view(["GET", "POST"])
def tasks_list(request):
    """
    GET: لیست وظایف با فیلتر
    POST: ساخت وظیفه جدید
    """
    if request.method == "GET":
        # Filters
        assigned_to = request.GET.get("assigned_to")
        status = request.GET.get("status")
        priority = request.GET.get("priority")
        customer_id = request.GET.get("customer")
        pinned_only = request.GET.get("pinned") == "true"
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 50))

        qs = Task.objects.select_related("assigned_to", "created_by", "customer", "sale").all()

        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        else:
            # Default: tasks assigned to current user
            qs = qs.filter(assigned_to=request.user)

        if status and status != "all":
            qs = qs.filter(status=status)
        else:
            # Default: exclude completed and cancelled
            qs = qs.exclude(status__in=[Task.STATUS_COMPLETED, Task.STATUS_CANCELLED])

        if priority and priority != "all":
            qs = qs.filter(priority=priority)

        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        if pinned_only:
            qs = qs.filter(pinned=True)

        total = qs.count()
        tasks = qs[offset : offset + limit]

        results = [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "priority_display": task.get_priority_display(),
                "status": task.status,
                "status_display": task.get_status_display(),
                "assigned_to_id": task.assigned_to_id,
                "assigned_to_name": task.assigned_to.get_full_name()
                or task.assigned_to.username,
                "created_by_id": task.created_by_id,
                "created_by_name": task.created_by.get_full_name()
                or task.created_by.username,
                "customer_id": task.customer_id,
                "customer_name": task.customer.name if task.customer else None,
                "sale_id": task.sale_id,
                "sale_code": task.sale.sale_code if task.sale else None,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "reminder_at": task.reminder_at.isoformat() if task.reminder_at else None,
                "reminder_sent": task.reminder_sent,
                "pinned": task.pinned,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }
            for task in tasks
        ]

        return JsonResponse({"ok": True, "data": {"results": results, "total": total}})

    # POST: create new task
    data = parse_json(request)
    task = Task.objects.create(
        title=data["title"],
        description=data.get("description", ""),
        priority=data.get("priority", Task.PRIORITY_MEDIUM),
        status=data.get("status", Task.STATUS_TODO),
        assigned_to_id=data.get("assigned_to_id") or request.user.id,
        created_by=request.user,
        customer_id=data.get("customer_id"),
        sale_id=data.get("sale_id"),
        due_date=data.get("due_date"),
        reminder_at=data.get("reminder_at"),
        pinned=data.get("pinned", False),
    )

    # Create activity
    Activity.objects.create(
        activity_type=Activity.ACTIVITY_TASK_CREATED,
        title=f"وظیفه ایجاد شد: {task.title}",
        description=task.description,
        user=request.user,
        customer_id=task.customer_id,
        sale_id=task.sale_id,
        task=task,
        occurred_at=timezone.now(),
    )

    return success(
        {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
        }
    )


@api_view(["PUT", "DELETE"])
def task_detail(request, task_id):
    """
    PUT: ویرایش وظیفه
    DELETE: حذف وظیفه
    """
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"ok": False, "error": "وظیفه یافت نشد."}, status=404)

    if request.method == "PUT":
        data = parse_json(request)

        if "title" in data:
            task.title = data["title"]
        if "description" in data:
            task.description = data["description"]
        if "priority" in data:
            task.priority = data["priority"]
        if "status" in data:
            old_status = task.status
            task.status = data["status"]
            if old_status != Task.STATUS_COMPLETED and task.status == Task.STATUS_COMPLETED:
                task.completed_at = timezone.now()
                # Create activity
                Activity.objects.create(
                    activity_type=Activity.ACTIVITY_TASK_COMPLETED,
                    title=f"وظیفه انجام شد: {task.title}",
                    user=request.user,
                    customer_id=task.customer_id,
                    sale_id=task.sale_id,
                    task=task,
                    occurred_at=timezone.now(),
                )
        if "due_date" in data:
            task.due_date = data["due_date"]
        if "reminder_at" in data:
            task.reminder_at = data["reminder_at"]
        if "pinned" in data:
            task.pinned = data["pinned"]
        if "assigned_to_id" in data:
            task.assigned_to_id = data["assigned_to_id"]

        task.save()

        return success(
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "pinned": task.pinned,
            }
        )

    # DELETE
    task.delete()
    return success({})


@api_view(["POST"])
def task_complete(request, task_id):
    """علامت‌گذاری وظیفه به عنوان انجام شده"""
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"ok": False, "error": "وظیفه یافت نشد."}, status=404)

    task.status = Task.STATUS_COMPLETED
    task.completed_at = timezone.now()
    task.save()

    # Create activity
    Activity.objects.create(
        activity_type=Activity.ACTIVITY_TASK_COMPLETED,
        title=f"وظیفه انجام شد: {task.title}",
        user=request.user,
        customer_id=task.customer_id,
        sale_id=task.sale_id,
        task=task,
        occurred_at=timezone.now(),
    )

    return success({"id": task.id, "status": task.status})


@api_view(["POST"])
def task_pin(request, task_id):
    """پین/آنپین کردن وظیفه"""
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return fail("وظیفه یافت نشد.", status=404)

    data = parse_json(request)
    task.pinned = data.get("pinned", not task.pinned)
    task.save()

    return success({"id": task.id, "pinned": task.pinned})
