"""مدل DashboardWidget برای داشبوردهای قابل تنظیم."""

from django.conf import settings
from django.db import models


class DashboardWidget(models.Model):
    """ویجت قابل تنظیم داشبورد"""

    WIDGET_STAT_CARD = "stat_card"
    WIDGET_CHART_BAR = "chart_bar"
    WIDGET_CHART_LINE = "chart_line"
    WIDGET_CHART_PIE = "chart_pie"
    WIDGET_TABLE = "table"

    WIDGET_TYPE_CHOICES = [
        (WIDGET_STAT_CARD, "کارت آماری"),
        (WIDGET_CHART_BAR, "نمودار ستونی"),
        (WIDGET_CHART_LINE, "نمودار خطی"),
        (WIDGET_CHART_PIE, "نمودار دایره‌ای"),
        (WIDGET_TABLE, "جدول"),
    ]

    SIZE_SMALL = "small"
    SIZE_MEDIUM = "medium"
    SIZE_LARGE = "large"
    SIZE_WIDE = "wide"

    SIZE_CHOICES = [
        (SIZE_SMALL, "کوچک"),
        (SIZE_MEDIUM, "متوسط"),
        (SIZE_LARGE, "بزرگ"),
        (SIZE_WIDE, "عریض"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_widgets",
        help_text="کاربری که این ویجت را ساخته",
    )
    widget_type = models.CharField(
        max_length=40, choices=WIDGET_TYPE_CHOICES, db_index=True
    )
    title = models.CharField(max_length=120)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="تنظیمات ویجت: metric، time_range، filters و ...",
    )
    position = models.IntegerField(
        default=0, help_text="ترتیب نمایش ویجت", db_index=True
    )
    size = models.CharField(
        max_length=20, choices=SIZE_CHOICES, default=SIZE_MEDIUM
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user", "position"]
        verbose_name = "ویجت داشبورد"
        verbose_name_plural = "ویجت‌های داشبورد"
        indexes = [
            models.Index(fields=["user", "position"], name="ix_widget_user_pos"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"
