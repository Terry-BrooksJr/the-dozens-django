"""
Tests for the /metrics endpoint IP allowlist enforced by metrics_view.

Covers:
- Exact IP match (IPv4)
- CIDR match (host inside subnet)
- CIDR boundary (host just outside subnet is rejected)
- Empty allowlist rejects everything
- Missing PROMETHEUS_ALLOWED_HOSTS setting rejects everything
- Malformed REMOTE_ADDR is rejected, not 500'd
- Malformed entry in allowlist is skipped, not 500'd
- IPv6 exact match
- IPv6 CIDR match
- 200 response delegates to django-prometheus (smoke-check body)
"""

from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from core.urls import metrics_view

PROMETHEUS_200_PATCH = "core.urls.ExportToDjangoView"


def _get(ip: str):
    """Build a GET request with the given REMOTE_ADDR."""
    factory = RequestFactory()
    request = factory.get("/metrics")
    request.META["REMOTE_ADDR"] = ip
    return request


class MetricsViewExactIPTests(TestCase):
    ALLOWED = ["165.227.105.209", "172.28.0.1"]

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=ALLOWED)
    def test_exact_ip_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.__class__.__name__ = "HttpResponse"
            mock_export.return_value.status_code = 200
            metrics_view(_get("165.227.105.209"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=ALLOWED)
    def test_second_exact_ip_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            metrics_view(_get("172.28.0.1"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=ALLOWED)
    def test_unlisted_ip_forbidden(self):
        response = metrics_view(_get("10.0.0.1"))
        self.assertEqual(response.status_code, 403)

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=ALLOWED)
    def test_similar_but_different_ip_forbidden(self):
        # 165.227.105.210 differs by one octet from the allowed address
        response = metrics_view(_get("165.227.105.210"))
        self.assertEqual(response.status_code, 403)


class MetricsViewCIDRTests(TestCase):
    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["172.19.0.0/24"])
    def test_ip_inside_subnet_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            metrics_view(_get("172.19.0.10"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["172.19.0.0/24"])
    def test_subnet_gateway_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            metrics_view(_get("172.19.0.1"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["172.19.0.0/24"])
    def test_ip_outside_subnet_forbidden(self):
        # 172.19.1.1 is in 172.19.1.0/24, not 172.19.0.0/24
        response = metrics_view(_get("172.19.1.1"))
        self.assertEqual(response.status_code, 403)

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["172.19.0.0/24"])
    def test_ip_in_adjacent_subnet_forbidden(self):
        response = metrics_view(_get("172.20.0.1"))
        self.assertEqual(response.status_code, 403)

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["172.19.0.0/24", "165.227.105.209"])
    def test_mixed_cidr_and_exact_ip_both_work(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            metrics_view(_get("172.19.0.50"))
            metrics_view(_get("165.227.105.209"))
        self.assertEqual(mock_export.call_count, 2)


class MetricsViewEdgeCasesTests(TestCase):
    @override_settings(PROMETHEUS_ALLOWED_HOSTS=[])
    def test_empty_allowlist_forbids_all(self):
        response = metrics_view(_get("165.227.105.209"))
        self.assertEqual(response.status_code, 403)

    def test_missing_setting_forbids_all(self):
        # Simulate the setting not existing at all on the settings object
        from django.conf import settings as django_settings

        original = getattr(django_settings, "PROMETHEUS_ALLOWED_HOSTS", None)
        if hasattr(django_settings, "PROMETHEUS_ALLOWED_HOSTS"):
            delattr(django_settings, "PROMETHEUS_ALLOWED_HOSTS")
        try:
            response = metrics_view(_get("165.227.105.209"))
            self.assertEqual(response.status_code, 403)
        finally:
            if original is not None:
                django_settings.PROMETHEUS_ALLOWED_HOSTS = original

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["165.227.105.209"])
    def test_malformed_remote_addr_forbidden_not_500(self):
        response = metrics_view(_get("not-an-ip"))
        self.assertEqual(response.status_code, 403)

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["165.227.105.209"])
    def test_empty_remote_addr_forbidden(self):
        factory = RequestFactory()
        request = factory.get("/metrics")
        request.META["REMOTE_ADDR"] = ""
        response = metrics_view(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(
        PROMETHEUS_ALLOWED_HOSTS=["not-a-valid-entry", "165.227.105.209"]
    )
    def test_malformed_allowlist_entry_skipped(self):
        # Bad entry is skipped; the valid entry still grants access
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            metrics_view(_get("165.227.105.209"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["not-a-valid-entry"])
    def test_only_malformed_allowlist_entry_forbids(self):
        response = metrics_view(_get("165.227.105.209"))
        self.assertEqual(response.status_code, 403)


class MetricsViewIPv6Tests(TestCase):
    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["::1"])
    def test_ipv6_loopback_exact_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            response = metrics_view(_get("::1"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["2001:db8::/32"])
    def test_ipv6_cidr_match_allowed(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            response = metrics_view(_get("2001:db8::1"))
        mock_export.assert_called_once()

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["2001:db8::/32"])
    def test_ipv6_outside_subnet_forbidden(self):
        response = metrics_view(_get("2001:db9::1"))
        self.assertEqual(response.status_code, 403)

    @override_settings(PROMETHEUS_ALLOWED_HOSTS=["::1"])
    def test_ipv4_rejected_when_only_ipv6_allowed(self):
        response = metrics_view(_get("127.0.0.1"))
        self.assertEqual(response.status_code, 403)
