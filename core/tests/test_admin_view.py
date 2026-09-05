"""
Tests for core.admin_view.grafana_dashboard_view.

Covers:
- Anonymous users are redirected to the admin login page (never see the dashboard).
- Authenticated non-staff users are redirected to the admin login page.
- Staff users get a 200 response rendering the Grafana iframe with the
  expected embed URL, using the admin site's own template chrome.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

DASHBOARD_URL_NAME = "admin-grafana-dashboard"
GRAFANA_URL = (
    "https://grafana.yo-momma.io/public-dashboards/3691683c85b749c989b9f3339b52a600"
)


class GrafanaDashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="staffer",
            email="staffer@example.com",
            password="pw12345",
            is_staff=True,
        )
        cls.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="pw12345"
        )

    def test_anonymous_user_is_redirected_to_admin_login(self):
        response = self.client.get(reverse(DASHBOARD_URL_NAME))

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_user_is_redirected_to_admin_login(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(reverse(DASHBOARD_URL_NAME))

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_staff_user_gets_200(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse(DASHBOARD_URL_NAME))

        self.assertEqual(response.status_code, 200)

    def test_staff_user_response_contains_grafana_url(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse(DASHBOARD_URL_NAME))

        self.assertContains(response, GRAFANA_URL)

    def test_staff_user_response_uses_dashboard_title(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse(DASHBOARD_URL_NAME))

        self.assertContains(response, "Observability Dashboard")
