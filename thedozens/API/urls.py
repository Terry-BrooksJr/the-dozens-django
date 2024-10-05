from API.views import InsultsCategoriesViewSet, MyInsultsViewSet, RandomInsultViewSet
from django.urls import re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"my-insults", MyInsultsViewSet, basename="my-insults")
router.register(
    r"insults/categories", InsultsCategoriesViewSet, basename="insult-categories"
)
router.register(r"insults", InsultsCategoriesViewSet, basename="insults")
router.register(r"insults/random", RandomInsultViewSet, basename="random-insult")

urlpatterns = router.urls
# from API import views

urlpatterns += [
    re_path(r"^schema$", SpectacularAPIView.as_view(), name="schema"),
    re_path(
        r"^swagger$", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"
    ),
    re_path(r"^docs$", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
# urlpatterns = [
#     re_path(
#         r"^insults/categories$",
#         views.InsultCategories.as_view(),
#         name="insult-categories",
#     ),
#     re_path(
#         r"^insults/category/<str:category>$",
#         views.InsultsCategoriesListView.as_view(),
#         name="List_View",
#     ),
#     re_path(r"^user/insults$", views.MyInsults.as_view(), name="users_submitted_jokes"),
#     re_path(r"^insults/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
#     re_path(r"^insult$", views.RandomInsultView.as_view(), name="Random-Unfiltered"),
