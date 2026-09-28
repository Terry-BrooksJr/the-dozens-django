# pyrefly: ignore-errors
"""Django app configuration for the public insult API."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """AppConfig for ``applications.API``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.API"

    def ready(self):
        """Django lifecycle hook: initialize cache-invalidation metrics."""
        # pylint: disable=all
        self._init_metrics()

    @staticmethod
    def _init_metrics() -> None:
        """Register cache-invalidation metrics if the metrics module is importable."""
        try:
            from common.metrics import init_cache_invalidation_metrics

            init_cache_invalidation_metrics()
        except ImportError:
            pass
