from django.apps import AppConfig
from django.conf import settings

from .client import configure_launchdarkly


class LDIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.ld_integration"

    def ready(self):
        configure_launchdarkly(
            sdk_key=getattr(settings, "LAUNCHDARKLY_SDK_KEY", ""),
            enabled=getattr(settings, "LAUNCHDARKLY_ENABLED", True),
            obs_enabled=getattr(settings, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", False),
            service_name=getattr(
                settings, "LAUNCHDARKLY_SERVICE_NAME", "django-service"
            ),
            service_version=getattr(settings, "LAUNCHDARKLY_SERVICE_VERSION", "dev"),
        )
