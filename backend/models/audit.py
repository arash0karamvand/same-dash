"""Relational audit events and explicit target tables."""

from django.conf import settings
from django.db import models


class AuditEntityType(models.Model):
    code = models.SlugField(max_length=40, primary_key=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.code


class AuditEvent(models.Model):
    ACTION_CHOICES = [
        ("create", "ایجاد"),
        ("update", "ویرایش"),
        ("delete", "حذف"),
        ("approve", "تایید"),
        ("reject", "رد"),
        ("sale", "فروش"),
        ("payment", "دریافت پرداخت"),
        ("check_in", "ثبت حضور"),
        ("check_out", "پایان کار"),
        ("login", "ورود"),
        ("logout", "خروج"),
        ("sms", "پیامک"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    entity_type_ref = models.ForeignKey(
        AuditEntityType,
        db_column="entity_type",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="events",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    is_executive_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="ix_audit_action_date"),
            models.Index(fields=["user", "created_at"], name="ix_audit_user_date"),
        ]

    @property
    def entity_type(self):
        if self.entity_type_ref_id:
            return self.entity_type_ref_id
        for relation, label in (
            ("order_target", "Sale"),
            ("office_order_target", "OfficeOrder"),
            ("factory_order_target", "FactoryOrder"),
            ("customer_target", "Customer"),
            ("journal_target", "JournalEntry"),
            ("material_target", "Material"),
            ("product_target", "Product"),
            ("product_category_target", "ProductCategory"),
            ("seller_target", "Seller"),
            ("attendance_target", "StaffAttendance"),
            ("installment_target", "SaleInstallment"),
            ("loyalty_level_target", "LoyaltyLevel"),
            ("reminder_campaign_target", "ReminderCampaign"),
            ("role_definition_target", "RoleDefinition"),
            ("subject_user_target", "User"),
        ):
            if hasattr(self, relation):
                return label
        return ""

    @entity_type.setter
    def entity_type(self, value):
        self.entity_type_ref_id = value or None

    @property
    def entity_id(self):
        for relation in (
            "order_target",
            "office_order_target",
            "factory_order_target",
            "customer_target",
            "journal_target",
            "material_target",
            "product_target",
            "product_category_target",
            "seller_target",
            "attendance_target",
            "installment_target",
            "loyalty_level_target",
            "reminder_campaign_target",
            "role_definition_target",
            "subject_user_target",
        ):
            target = getattr(self, relation, None)
            if target:
                return str(target.target_id)
        return ""

    @entity_id.setter
    def entity_id(self, value):
        self._legacy_entity_id = value

    def __str__(self):
        return self.message


class AuditOrderTarget(models.Model):
    event = models.OneToOneField(AuditEvent, on_delete=models.CASCADE, related_name="order_target")
    target = models.ForeignKey("backend.Sale", on_delete=models.PROTECT)


class AuditOfficeOrderTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="office_order_target"
    )
    target = models.ForeignKey("backend.Sale", on_delete=models.PROTECT)


class AuditFactoryOrderTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="factory_order_target"
    )
    target = models.ForeignKey("backend.Sale", on_delete=models.PROTECT)


class AuditCustomerTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="customer_target"
    )
    target = models.ForeignKey("backend.Customer", on_delete=models.PROTECT)


class AuditJournalTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="journal_target"
    )
    target = models.ForeignKey("backend.JournalLine", on_delete=models.PROTECT)


class AuditMaterialTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="material_target"
    )
    target = models.ForeignKey("backend.Material", on_delete=models.PROTECT)


class AuditProductTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="product_target"
    )
    target = models.ForeignKey("backend.Product", on_delete=models.PROTECT)


class AuditProductCategoryTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="product_category_target"
    )
    target = models.ForeignKey("backend.ProductCategory", on_delete=models.PROTECT)


class AuditSellerTarget(models.Model):
    event = models.OneToOneField(AuditEvent, on_delete=models.CASCADE, related_name="seller_target")
    target = models.ForeignKey("backend.Seller", on_delete=models.PROTECT)


class AuditAttendanceTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="attendance_target"
    )
    target = models.ForeignKey("backend.StaffAttendance", on_delete=models.PROTECT)


class AuditInstallmentTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="installment_target"
    )
    target = models.ForeignKey("backend.SaleInstallment", on_delete=models.PROTECT)


class AuditLoyaltyLevelTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="loyalty_level_target"
    )
    target = models.ForeignKey("backend.LoyaltyLevel", on_delete=models.PROTECT)


class AuditReminderCampaignTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="reminder_campaign_target"
    )
    target = models.ForeignKey("backend.ReminderCampaign", on_delete=models.PROTECT)


class AuditRoleDefinitionTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="role_definition_target"
    )
    target = models.ForeignKey("backend.RoleDefinition", on_delete=models.PROTECT)


class AuditUserTarget(models.Model):
    event = models.OneToOneField(
        AuditEvent, on_delete=models.CASCADE, related_name="subject_user_target"
    )
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class AuditLog(AuditEvent):
    """Legacy public name; no second audit table."""

    class Meta:
        proxy = True
