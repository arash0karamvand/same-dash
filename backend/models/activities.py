"""مدل‌های Activity و Task برای مدیریت تایم‌لاین فعالیت‌ها و وظایف."""

from django.conf import settings
from django.db import models


class Activity(models.Model):
    """رویداد یا فعالیت قابل مشاهده در تایم‌لاین"""

    ACTIVITY_CALL = "call"
    ACTIVITY_EMAIL = "email"
    ACTIVITY_MEETING = "meeting"
    ACTIVITY_NOTE = "note"
    ACTIVITY_SALE = "sale"
    ACTIVITY_TASK_CREATED = "task_created"
    ACTIVITY_TASK_COMPLETED = "task_completed"
    ACTIVITY_ORDER_STATUS = "order_status"
    ACTIVITY_CUSTOMER_CREATED = "customer_created"

    ACTIVITY_TYPE_CHOICES = [
        (ACTIVITY_CALL, "تماس تلفنی"),
        (ACTIVITY_EMAIL, "ایمیل"),
        (ACTIVITY_MEETING, "جلسه"),
        (ACTIVITY_NOTE, "یادداشت"),
        (ACTIVITY_SALE, "فروش"),
        (ACTIVITY_TASK_CREATED, "وظیفه ایجاد شد"),
        (ACTIVITY_TASK_COMPLETED, "وظیفه انجام شد"),
        (ACTIVITY_ORDER_STATUS, "تغییر وضعیت سفارش"),
        (ACTIVITY_CUSTOMER_CREATED, "مشتری جدید"),
    ]

    activity_type = models.CharField(max_length=40, choices=ACTIVITY_TYPE_CHOICES, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Relations
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
        help_text="کاربری که این فعالیت را ثبت کرده",
    )
    customer = models.ForeignKey(
        "Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )
    sale = models.ForeignKey(
        "Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )
    task = models.ForeignKey(
        "Task",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="داده‌های اضافی مانند مدت تماس، موضوع جلسه و ...",
    )
    occurred_at = models.DateTimeField(help_text="زمان وقوع فعالیت")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "فعالیت"
        verbose_name_plural = "فعالیت‌ها"
        indexes = [
            models.Index(fields=["user", "-occurred_at"], name="ix_activity_user_date"),
            models.Index(
                fields=["customer", "-occurred_at"], name="ix_activity_customer"
            ),
            models.Index(fields=["activity_type", "-occurred_at"], name="ix_activity_type"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_activity_type_display()})"


class Task(models.Model):
    """وظیفه قابل تخصیص با یادآور و اولویت"""

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "کم"),
        (PRIORITY_MEDIUM, "متوسط"),
        (PRIORITY_HIGH, "زیاد"),
        (PRIORITY_URGENT, "فوری"),
    ]

    STATUS_TODO = "todo"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_TODO, "انجام نشده"),
        (STATUS_IN_PROGRESS, "در حال انجام"),
        (STATUS_COMPLETED, "انجام شده"),
        (STATUS_CANCELLED, "لغو شده"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_TODO, db_index=True
    )

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
        help_text="کاربری که این وظیفه به او محول شده",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        help_text="کاربری که این وظیفه را ایجاد کرده",
    )

    # Relations
    customer = models.ForeignKey(
        "Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    sale = models.ForeignKey(
        "Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )

    # Dates
    due_date = models.DateTimeField(
        null=True, blank=True, help_text="سررسید وظیفه", db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Reminder
    reminder_at = models.DateTimeField(
        null=True, blank=True, help_text="زمان یادآوری", db_index=True
    )
    reminder_sent = models.BooleanField(default=False)
    pinned = models.BooleanField(
        default=False, help_text="پین کردن برای اولویت بالا", db_index=True
    )

    class Meta:
        ordering = ["-pinned", "-priority", "due_date", "-created_at"]
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"
        indexes = [
            models.Index(
                fields=["assigned_to", "status", "-due_date"], name="ix_task_assigned"
            ),
            models.Index(fields=["pinned", "-priority"], name="ix_task_priority"),
            models.Index(fields=["status", "-created_at"], name="ix_task_status"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
