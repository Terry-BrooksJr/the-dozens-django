from API import views
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path(
        "insults/categories",
        views.InsultCategories.as_view(),
        name="insult-categories",
    ),
    path(
        "insults/categories/<str:category>",
        views.InsultsCategoriesListView.as_view(),
        name="List_View",
    ),
    path("insult/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
    path("insult", views.randomUnfilteredInsult, name="Random-Unfiltered"),
]
