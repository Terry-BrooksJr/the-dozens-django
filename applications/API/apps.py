# pyrefly: ignore-errors
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.API"

    def ready(self):
        # pylint: disable=all
        self._pre_register_metric_labels()

    @staticmethod
    def _pre_register_metric_labels() -> None:
        """
        Touch every known (cache_prefix, reason) label combination so that
        ``cache_invalidations_total`` appears in /metrics as a zero-series
        from the very first scrape.

        Without this, prometheus_client only emits label combos it has seen
        incremented at least once — meaning dashboards and rate-based alerts
        are blind to the metric until an actual invalidation occurs, which can
        be infrequent or never in low-write environments.

        The list is kept in sync with:
          - cache_manager prefixes registered in forms.py, serializers.py,
            and performance.py (CachedModelViewSet)
          - the sender.__name__ pattern-fallback path in performance.invalidate_cache
        """
        try:
            from common.cache_managers import cache_registry
            from common.metrics import _pre_register_invalidation_labels

            # Collect prefixes from live registry (managers registered at module import).
            registry_prefixes = tuple(
                manager.cache_prefix
                for manager in cache_registry.values()
                if hasattr(manager, "cache_prefix")
            )

            # Also cover the model-name fallback path (sender.__name__) for models
            # that may not have a registered cache manager but are watched by signals.
            static_prefixes = (
                "Insult",
                "InsultCategory",
                "Insult_view",
                "Insult_categories",
            )

            all_prefixes = tuple(set(registry_prefixes + static_prefixes))
            _pre_register_invalidation_labels(all_prefixes)
        except Exception:
            # Never block startup — metrics pre-registration is best-effort.
            pass
