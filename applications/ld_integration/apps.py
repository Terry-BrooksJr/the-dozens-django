import logging

from django.apps import AppConfig
from django.conf import settings

from common.helpers import InterceptHandler

from .client import configure_launchdarkly


class LDIntegrationConfig(AppConfig):
    """AppConfig for the LaunchDarkly integration app.

    Owns process startup for LaunchDarkly: bridging stdlib logging into
    Loguru before the SDK's Observability plugin can install its own
    competing logging config, then initializing the LaunchDarkly client from
    Django settings.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.ld_integration"

    def ready(self):
        """Django lifecycle hook: bridge stdlib logging, then the LaunchDarkly client.

        Runs once Django has loaded all apps. Order matters here (see the
        inline note below): the root logger's handler must be replaced
        before `configure_launchdarkly()` so our handler wins over the one
        the Observability plugin would otherwise install.
        """
        # Must run before configure_launchdarkly(): once the LaunchDarkly
        # Observability plugin instruments logging, it calls
        # logging.basicConfig(format=<OTel trace_id/span_id format>, ...) to
        # correlate stdlib logs (e.g. django.request) with traces.
        #
        # logging.basicConfig() only touches the root logger if it has *no*
        # handlers yet - by this point in startup, Django's own LOGGING_CONFIG
        # (dictConfig) or pytest's logging capture may already have attached
        # one, which would silently make basicConfig() a no-op and leave
        # InterceptHandler never installed. Set the handler list directly
        # instead, so this always wins regardless of what ran before it.
        # InterceptHandler forwards every stdlib record into Loguru's own
        # sinks (console, file, Loki, LaunchDarkly Observability) instead of
        # leaving third-party logs (ldobserve, ldclient, django, ...)
        # confined to a separate plain-formatted handler - see
        # InterceptHandler's docstring for how it avoids double-reporting to
        # LaunchDarkly Observability.
        root_logger = logging.getLogger()
        root_logger.handlers = [InterceptHandler()]
        root_logger.setLevel(logging.INFO)
        configure_launchdarkly(
            sdk_key=getattr(settings, "LAUNCHDARKLY_SDK_KEY", ""),
            enabled=getattr(settings, "LAUNCHDARKLY_ENABLED", True),
            obs_enabled=getattr(settings, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", False),
            service_name=getattr(
                settings, "LAUNCHDARKLY_SERVICE_NAME", "django-service"
            ),
            service_version=getattr(settings, "LAUNCHDARKLY_SERVICE_VERSION", "dev"),
        )
