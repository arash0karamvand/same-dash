from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from backend.models import (
    AuditCustomerTarget,
    Branch,
    Customer,
    MenuSection,
    Permission,
    RoleDefinition,
    StaffProfile,
)
from logic.audit import list_audit_logs, log_action


User = get_user_model()


class AccessAuditRefactorTest(TestCase):
    def test_branch_fk_keeps_code_contract(self):
        user = User.objects.create_user(username="branch-user")
        profile = StaffProfile.objects.create(user=user, branch_id="branch_1")

        self.assertEqual(profile.branch_id, "branch_1")
        self.assertEqual(profile.branch.code, "branch_1")
        self.assertIsInstance(profile.branch, Branch)

    def test_role_hierarchy_rejects_cycle(self):
        parent = RoleDefinition.objects.create(slug="parent-role", label="Parent")
        child = RoleDefinition.objects.create(
            slug="child-role", label="Child", parent=parent
        )
        parent.parent = child

        with self.assertRaises(ValidationError):
            parent.save()

    def test_permissions_are_relation_rows(self):
        permission = Permission.objects.create(code="test_permission", label="Test")
        role = RoleDefinition.objects.create(slug="test-role", label="Test")
        role.permission_set.add(permission)
        section = MenuSection.objects.create(
            section_id="test-section", label="Test", page_key="test"
        )
        section.menu_permissions.add(permission)

        self.assertEqual(role.permissions, ["test_permission"])
        self.assertEqual(section.menu_permission_codes, ["test_permission"])

    def test_audit_target_and_legacy_contract(self):
        customer = Customer.objects.create(full_name="Audit", phone="09120000123")
        event = log_action(
            None,
            "update",
            "Customer updated",
            entity_type="Customer",
            entity_id=customer.id,
        )

        self.assertTrue(
            AuditCustomerTarget.objects.filter(event=event, target=customer).exists()
        )
        self.assertEqual(event.entity_type, "Customer")
        self.assertEqual(event.entity_id, str(customer.id))
        payload = list_audit_logs({"entity_type": "Customer"})
        self.assertEqual(payload["results"][0]["entity_type"], "Customer")
        self.assertEqual(payload["results"][0]["entity_id"], str(customer.id))
