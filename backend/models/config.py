"""Reference data, access control, and menu configuration."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Branch(models.Model):
    code = models.SlugField("کد شعبه", max_length=40, unique=True)
    label = models.CharField("نام شعبه", max_length=80)
    color = models.CharField("رنگ", max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)
    work_start = models.TimeField("شروع ساعت کاری", null=True, blank=True)
    work_end = models.TimeField("پایان ساعت کاری", null=True, blank=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class LookupOption(models.Model):
    category = models.CharField(max_length=40, db_index=True)
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["category", "sort_order", "label"]
        constraints = [
            models.UniqueConstraint(fields=["category", "code"], name="uq_lookup_category_code"),
        ]

    def __str__(self):
        return f"{self.category}:{self.code}"


class CodeLabelReference(models.Model):
    code = models.SlugField(max_length=40, primary_key=True)
    label = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.code


class PaymentMethod(CodeLabelReference):
    pass


class PaymentStatus(CodeLabelReference):
    pass


class OrderKind(CodeLabelReference):
    pass


class OrderStatus(CodeLabelReference):
    pass


class AccountingMode(CodeLabelReference):
    pass


class InstallmentStatus(CodeLabelReference):
    pass


class AttendanceStatus(CodeLabelReference):
    pass


class ApprovalStatus(CodeLabelReference):
    pass


class MaterialStatus(CodeLabelReference):
    pass


class SmsStatus(CodeLabelReference):
    pass


class SmsType(CodeLabelReference):
    pass


class JournalEntryType(CodeLabelReference):
    pass


class JournalEntryStatus(CodeLabelReference):
    pass


class Permission(models.Model):
    code = models.SlugField(max_length=100, unique=True)
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class RoleDefinition(models.Model):
    slug = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    is_builtin = models.BooleanField(default=False)
    needs_branch = models.BooleanField(default=False)
    grants_full_access = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    color = models.CharField(max_length=20, default="#6366f1")
    sort_order = models.PositiveIntegerField(default=0)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    department = models.CharField(max_length=20, blank=True, default="")
    permission_set = models.ManyToManyField(
        Permission, through="RolePermission", related_name="roles", blank=True
    )

    class Meta:
        ordering = ["sort_order", "label"]

    @property
    def permissions(self):
        if not self.pk:
            return getattr(self, "_permission_codes", [])
        return list(self.permission_set.values_list("code", flat=True))

    @permissions.setter
    def permissions(self, value):
        self._permission_codes = list(value or [])

    def clean(self):
        if not self.parent_id:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "Role hierarchy cannot contain a cycle."})
        seen = {self.pk} if self.pk else set()
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk in seen:
                raise ValidationError({"parent": "Role hierarchy cannot contain a cycle."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        codes = getattr(self, "_permission_codes", None)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) - {"permissions"}
            if not kwargs["update_fields"]:
                kwargs.pop("update_fields")
        with transaction.atomic():
            self.clean()
            super().save(*args, **kwargs)
            _rebuild_role_closure()
            if codes is not None:
                permissions = [
                    Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
                    for code in codes
                ]
                self.permission_set.set(permissions)
                del self._permission_codes

    def __str__(self):
        return self.label


class RolePermission(models.Model):
    pk = models.CompositePrimaryKey("role", "permission")
    role = models.ForeignKey(RoleDefinition, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)


class RoleClosure(models.Model):
    pk = models.CompositePrimaryKey("ancestor", "descendant")
    ancestor = models.ForeignKey(
        RoleDefinition, on_delete=models.CASCADE, related_name="role_descendants"
    )
    descendant = models.ForeignKey(
        RoleDefinition, on_delete=models.CASCADE, related_name="role_ancestors"
    )
    depth = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(depth__gte=0), name="ck_role_depth_nonnegative"),
        ]
        indexes = [models.Index(fields=["descendant", "depth"], name="ix_role_desc_depth")]


class UserAccessProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_profile"
    )
    primary_department = models.CharField(max_length=20, blank=True, default="")
    permission_set = models.ManyToManyField(
        Permission, through="UserPermission", related_name="users", blank=True
    )

    @property
    def extra_permissions(self):
        if not self.pk:
            return getattr(self, "_permission_codes", [])
        return list(self.permission_set.values_list("code", flat=True))

    @extra_permissions.setter
    def extra_permissions(self, value):
        self._permission_codes = list(value or [])

    def save(self, *args, **kwargs):
        codes = getattr(self, "_permission_codes", None)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) - {"extra_permissions"}
            if not kwargs["update_fields"]:
                kwargs.pop("update_fields")
        super().save(*args, **kwargs)
        if codes is not None:
            permissions = [
                Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
                for code in codes
            ]
            self.permission_set.set(permissions)
            del self._permission_codes


class UserPermission(models.Model):
    pk = models.CompositePrimaryKey("access_profile", "permission")
    access_profile = models.ForeignKey(UserAccessProfile, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)


class MenuSection(models.Model):
    section_id = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    icon = models.CharField(max_length=16, default="📄")
    page_key = models.SlugField(max_length=40)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    system_admin = models.BooleanField(default=False)
    menu_permissions = models.ManyToManyField(
        Permission, through="MenuPermission", related_name="menu_sections", blank=True
    )
    section_permissions = models.ManyToManyField(
        Permission, through="SectionPermission", related_name="protected_sections", blank=True
    )

    class Meta:
        ordering = ["sort_order", "label"]

    @property
    def menu_permission_codes(self):
        if not self.pk:
            return getattr(self, "_menu_permission_codes", [])
        return list(self.menu_permissions.values_list("code", flat=True))

    @menu_permission_codes.setter
    def menu_permission_codes(self, value):
        self._menu_permission_codes = list(value or [])

    @property
    def section_permission_codes(self):
        if not self.pk:
            return getattr(self, "_section_permission_codes", [])
        return list(self.section_permissions.values_list("code", flat=True))

    @section_permission_codes.setter
    def section_permission_codes(self, value):
        self._section_permission_codes = list(value or [])

    def save(self, *args, **kwargs):
        menu_codes = getattr(self, "_menu_permission_codes", None)
        section_codes = getattr(self, "_section_permission_codes", None)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) - {
                "menu_permission_codes",
                "section_permission_codes",
            }
            if not kwargs["update_fields"]:
                kwargs.pop("update_fields")
        super().save(*args, **kwargs)
        for codes, relation, cache_name in (
            (menu_codes, self.menu_permissions, "_menu_permission_codes"),
            (section_codes, self.section_permissions, "_section_permission_codes"),
        ):
            if codes is not None:
                permissions = [
                    Permission.objects.get_or_create(code=code, defaults={"label": code})[0]
                    for code in codes
                ]
                relation.set(permissions)
                delattr(self, cache_name)

    def __str__(self):
        return self.label


class MenuPermission(models.Model):
    pk = models.CompositePrimaryKey("menu_section", "permission")
    menu_section = models.ForeignKey(MenuSection, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)


class SectionPermission(models.Model):
    pk = models.CompositePrimaryKey("menu_section", "permission")
    menu_section = models.ForeignKey(MenuSection, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)


def _rebuild_role_closure():
    parents = dict(RoleDefinition.objects.values_list("id", "parent_id"))
    paths = []
    for descendant_id in parents:
        seen = {descendant_id}
        ancestor_id = descendant_id
        depth = 0
        while ancestor_id is not None:
            paths.append(
                RoleClosure(
                    ancestor_id=ancestor_id,
                    descendant_id=descendant_id,
                    depth=depth,
                )
            )
            ancestor_id = parents.get(ancestor_id)
            depth += 1
            if ancestor_id in seen:
                raise ValidationError("Role hierarchy cannot contain a cycle.")
            seen.add(ancestor_id)
    RoleClosure.objects.all().delete()
    RoleClosure.objects.bulk_create(paths)
