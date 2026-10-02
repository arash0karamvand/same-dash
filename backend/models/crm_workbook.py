"""ردیف‌های CRM مطابق برگه‌های اکسل CRM 1405."""

from django.conf import settings
from django.db import models

from logic.crm_workbook_schema import CRM_SHEETS


class CrmWorkbookRow(models.Model):
    SOURCE_EXCEL = "excel"
    SOURCE_MANUAL = "manual"
    SOURCE_SALE_SYNC = "sale_sync"
    SOURCE_CHOICES = [
        (SOURCE_EXCEL, "اکسل"),
        (SOURCE_MANUAL, "دستی"),
        (SOURCE_SALE_SYNC, "همگام با فروش"),
    ]

    sheet = models.CharField(
        max_length=32,
        choices=[(k, v) for k, v in CRM_SHEETS.items()],
        db_index=True,
    )
    invoice_ref = models.CharField(max_length=64, blank=True, default="", db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)
    sale = models.ForeignKey(
        "backend.Sale",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_workbook_rows",
    )
    source = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_workbook_edits",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sheet", "sort_order", "id"]
        indexes = [
            models.Index(fields=["sheet", "invoice_ref"], name="ix_crm_wb_sheet_inv"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "invoice_ref", "sort_order"],
                name="uq_crm_wb_sheet_inv_sort",
            ),
        ]

    def __str__(self):
        return f"{self.sheet}:{self.invoice_ref or self.pk}"
