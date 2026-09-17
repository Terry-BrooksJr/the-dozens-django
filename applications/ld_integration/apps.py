import logging

from django.apps import AppConfig
from django.conf import settings

from .client import configure_launchdarkly


class LDIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.ld_integration"

    def ready(self):
        # Must run before configure_launchdarkly(): once the LaunchDarkly
        # Observability plugin instruments logging, it calls
        # logging.basicConfig(format=<OTel trace_id/span_id format>, ...) to
        # correlate stdlib logs (e.g. django.request) with traces.
        # logging.basicConfig() is a no-op once the root logger already has a
        # handler, so configuring our own format here first keeps that OTel
        # format from taking over.
        logging.basicConfig(
            format=getattr(settings, "DEFAULT_LOG_FORMAT", "%(asctime)s %(levelname)s %(message)s"),
            level=logging.INFO,
        )
        configure_launchdarkly(
            sdk_key=getattr(settings, "LAUNCHDARKLY_SDK_KEY", ""),
            enabled=getattr(settings, "LAUNCHDARKLY_ENABLED", True),
            obs_enabled=getattr(settings, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", False),
            service_name=getattr(
                settings, "LAUNCHDARKLY_SERVICE_NAME", "django-service"
            ),
            service_version=getattr(settings, "LAUNCHDARKLY_SERVICE_VERSION", "dev"),
        )
