"""اعلان‌های درون‌برنامه‌ای به‌تفکیک بخش و گیرنده."""

from django.conf import settings
from django.db import models


class Notification(models.Model):
    SECTION_ATTENDANCE = "attendance"
    SECTION_SALES = "sales"
    SECTION_PRODUCTS = "products"
    SECTION_WAREHOUSE = "warehouse"
    SECTION_ORG = "org"
    SECTION_CHOICES = [
        (SECTION_ATTENDANCE, "حضور و غیاب"),
        (SECTION_SALES, "فروش"),
        (SECTION_PRODUCTS, "محصولات"),
        (SECTION_WAREHOUSE, "انبار"),
        (SECTION_ORG, "سازمانی"),
    ]

    ACTION_BRANCH_SWITCH = "approve_branch_switch"
    ACTION_ORG_TICKET = "org_ticket"
    ACTION_ORG_RESPONSIBILITY = "org_responsibility"

    section = models.CharField(max_length=40, choices=SECTION_CHOICES, db_index=True)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    action_type = models.CharField(max_length=40, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    target_permission = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_notifications",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["section", "created_at"], name="ix_notification_section"),
        ]

    def __str__(self):
        return self.title


class NotificationReceipt(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="receipts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_receipts"
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "user"], name="uq_notification_receipt_user"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_read", "notification"], name="ix_notif_receipt_user"),
        ]


class TicketMessage(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="ticket_messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["notification", "created_at"], name="ix_ticket_msg_note"),
        ]

    def __str__(self):
        return f"{self.notification_id}: {self.body[:40]}"
