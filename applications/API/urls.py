from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from applications.API.endpoints import (
    CreateInsultEndpoint,
    HealthEndpoint,
    InsultByCategoryEndpoint,
    InsultDetailsEndpoint,
    ListThemesAndCategoryEndpoint,
    PingEndpoint,
    RandomInsultEndpoint,
)

urlpatterns = [
    # Health / liveness
    path("ping/", PingEndpoint.as_view(), name="ping"),      # Traefik liveness probe
    path("health/", HealthEndpoint.as_view(), name="health"), # deep readiness check
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
    # Categories (static-ish)
    path(
        "categories/", ListThemesAndCategoryEndpoint.as_view(), name="list_categories"
    ),
    # Insults – collection first
    path("insults/new", CreateInsultEndpoint.as_view(), name="create_insult"),
    path("insults/random/", RandomInsultEndpoint.as_view(), name="random_insult"),
    path(
        "insults/category/<str:category_name>/",
        InsultByCategoryEndpoint.as_view(),
        name="insults_by_category",
    ),
    # Insults – member routes (catch-all; keep last among insult routes)
    path(
        "insults/<str:reference_id>/",
        InsultDetailsEndpoint.as_view(),
        name="insult_detail",
    ),
]
