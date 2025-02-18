from applications.API import views
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path(
        "insults/categories",
        views.InsultsCategoriesViewSet.as_view(),
        name="insult-categories",
    ),
    path(
        "insults/categories/<str:category>",
        views.InsultsCategoriesListView.as_view(),
        name="List_View",
    ),
    path("insult/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
    # path("insult", views.randomUnfilteredInsult, name="Random-Unfiltered"),
    path("", SpectacularAPIView.as_view(), name="schema"),
    path("swagger", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc", SpectacularRedocView.as_view(), name="redoc"),
    path("user/insults", views.MyInsultsView.as_view(), name="my-insults-detail"),
]
