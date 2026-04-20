# pyrefly: ignore-errors
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.API"

    def ready(self):
        # pylint: disable=all
        self._init_metrics()

    @staticmethod
    def _init_metrics() -> None:
        try:
            from common.metrics import init_cache_invalidation_metrics

            init_cache_invalidation_metrics()
        except ImportError:
            pass
