from prometheus_client import Counter


class DozensMetrics:
    """Manages metrics tracking for the NHHC web application.

    This class provides a comprehensive metrics tracking system for monitoring various application events and performance indicators.
    It uses Prometheus-style counters and histograms to record submission attempts, cache interactions, and document processing metrics.

    Attributes:
        NAMESPACE (str): The base namespace for all metrics in the web application.
    """

    NAMESPACE = "dozens"

    def __init__(self):
        self.cached_queryset_hit = Counter(
            "cached_queryset_hit",
            "Number of requests served by a cached Queryset",
            ["model"],
        )
        self.cached_queryset_miss = Counter(
            "cached_queryset_miss",
            "Number of  requests not served by a cached Queryset",
            ["model"],
        )
        self.cached_queryset_evicted = Counter(
            "cached_queryset_evicted", "Number of cached Querysets evicted", ["model"]
        )

    def increment_cache(self, model: str, type: str) -> None:
        """Tracks cache performance metrics for different database models.

        This method increments the appropriate counter based on the cache interaction type,
        providing insights into cache hit, miss, and eviction rates for specific models.

        Args:
            model: The name of the database model being cached.
            type: The type of cache interaction ('hit', 'miss', or 'eviction').

        Returns:
            None
        """
        if type == "hit":
            self.cached_queryset_hit.labels(model=model).inc()
        elif type == "miss":
            self.cached_queryset_miss.labels(model=model).inc()
        elif type == "eviction":
            self.cached_queryset_evicted.labels(model=model).inc()


# Create a singleton instance for global use
metrics = DozensMetrics()
