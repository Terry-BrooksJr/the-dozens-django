from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from applications.API import endpoints

# router = DefaultRouter()
# router.register(r"insults", views.InsultViewSet, basename="insult")
# router.register(r"categories", views.CategoryViewSet, basename="category")

urlpatterns = [
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
    path("insult/<reference_id>", endpoints.InsultDetailsEndpoints.as_view()),
    path("insults/<category_name>", endpoints.InsultByCategoryEndpoint.as_view()),
    path("insults", endpoints.InsultListEndpoint.as_view()),
    path("insult", endpoints.RandomInsultView.as_view(), name="insult-random"),
    path("insult/categories", endpoints.ListCategoryView.as_view(), name="cat-list"),
]
