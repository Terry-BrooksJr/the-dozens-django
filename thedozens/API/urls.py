from API import views
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path(
        "insults/categories",
        views.InsultCategories.as_view(),
        name="insult-categories",
    ),
    path(
        "insults/category/<str:category>",
        views.InsultsCategoriesListView.as_view(),
        name="List_View",
    ),
    path("user/insults/", views.MyInsults.as_view(),name="users_submitted_jokes"),
    path("insults/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
    path("insult", views.RandomInsultView.as_view(), name="Random-Unfiltered"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("swagger", SpectacularSwaggerView.as_view(url_name='schema'), name="swagger"),
    path("docs", SpectacularRedocView.as_view(url_name='schema'), name="redoc")
]
