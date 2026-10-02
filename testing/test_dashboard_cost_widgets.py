import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from auth import roles
from testing.role_helpers import ensure_test_role


class DashboardCostWidgetTests(TestCase):
    def _client_with_permissions(self, username, permissions):
        ensure_test_role(username, permissions, label=username)
        user = get_user_model().objects.create_user(username=username, password="secret123")
        roles.assign_role(user, username)
        client = Client()
        client.login(username=username, password="secret123")
        return client

    def test_cost_widget_is_rejected_without_accounting_reports(self):
        client = self._client_with_permissions("factory_dash", ["view_dashboard", "view_factory_orders"])
        response = client.post(
            "/api/dashboard/widgets/",
            data=json.dumps({
                "widget_type": "stat_card",
                "title": "بهای تولید",
                "config": {"metric": "production_cost_summary", "time_range": "month"},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_accounting_reports_user_can_create_cost_widget(self):
        client = self._client_with_permissions(
            "accounting_dash",
            ["view_dashboard", "view_accounting", "view_reports"],
        )
        response = client.post(
            "/api/dashboard/widgets/",
            data=json.dumps({
                "widget_type": "stat_card",
                "title": "ارزش موجودی",
                "config": {"metric": "material_inventory_value", "time_range": "month"},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        metric = client.get("/api/dashboard/metrics/material_inventory_value/?time_range=month")
        self.assertEqual(metric.status_code, 200, metric.content)
