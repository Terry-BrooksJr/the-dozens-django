# pyrefly: ignore-errors
"""Django app configuration for the public insult API."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """AppConfig for ``applications.API``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.API"

    def ready(self):
        """Django lifecycle hook: register schema extensions, init cache metrics."""
        # pylint: disable=all
        import applications.API.schema  # noqa: F401  (registers drf-spectacular extensions)

        self._init_metrics()

    @staticmethod
    def _init_metrics() -> None:
        """Pre-register cache-invalidation metrics for every registered cache prefix."""
        try:
            from common.cache_managers import cache_registry
            from common.metrics import init_cache_invalidation_metrics

            init_cache_invalidation_metrics(
                manager.cache_prefix
                for manager in cache_registry.values()
                if hasattr(manager, "cache_prefix")
            )
        except ImportError:
            pass
