from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from applications.API.endpoints import CreateInsultView, InsultByCategoryEndpoint,ListCategoryView, RandomInsultView,InsultDetailsEndpoints, InsultListView


urlpatterns = [
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
    # Categories (static-ish)
    path("api/categories/", ListCategoryView.as_view(), name="list_categories"),
    # Insults – collection first
    path("api/insults/", InsultListView.as_view(), name="list_insults"),
    path(
        "api/insults/", CreateInsultView.as_view(), name="create_insult"
    ),  # same path, different method
    # Insults – custom collection routes with distinct prefixes (more specific than generic <reference_id>)
    path("api/insults/random", RandomInsultView.as_view(), name="random_insult"),
    path(
        "api/insults/category/<str:category_name>/",
        InsultByCategoryEndpoint.as_view(),
        name="insults_by_category",
    ),
    # Insults – member routes
    path(
        "api/insults/<str:reference_id>/",
        InsultDetailsEndpoints.as_view(),
        name="insult_detail",
    ),
]
