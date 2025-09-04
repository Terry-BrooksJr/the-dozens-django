from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from applications.API.endpoints import (
    CreateInsultEndpoint,
    InsultByCategoryEndpoint,
    InsultDetailsEndpoint,
    ListCategoryEndpoint,
    RandomInsultEndpoint,
)

urlpatterns = [
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
    # Categories (static-ish)
    path("categories/", ListCategoryEndpoint.as_view(), name="list_categories"),
    # Insults – collection first
    path("insults/new", CreateInsultEndpoint.as_view(), name="create_insult"),
    path("insults/random", RandomInsultEndpoint.as_view(), name="random_insult"),
    path(
        "insults/category/<str:category_name>/",
        InsultByCategoryEndpoint.as_view(),
        name="insults_by_category",
    ),
    # Insults – member routes
    path(
        "insults/<str:reference_id>/",
        InsultDetailsEndpoint.as_view(),
        name="insult_detail",
    ),
]
