from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from django.templatetags.static import static

from applications.API import views

router = DefaultRouter()
router.register(r"insults", views.InsultViewSet, basename="insult")
router.register(r"categories", views.CategoryViewSet, basename="category")

urlpatterns = [
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
] + router.urls
