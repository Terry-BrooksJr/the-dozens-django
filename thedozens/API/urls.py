from API import views
from django.urls import path
from drf_spectacular.views import (SpectacularAPIView,
                                   SpectacularSwaggerView)

urlpatterns = [
    path("insults/categories", views.InsultCatergories.as_view(), name="insult-categories"),
    path("insults/categories/<str:category>", views.InsultsCatergoriesListView.as_view(), name="List_View"),
    path("insult/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
<<<<<<< Updated upstream
    path("insult", views.randomUnfilteredInsult, name="Random-Unfiltered"),
=======
    # path("insult", views.randomUnfilteredInsult, name="Random-Unfiltered"),
    path('', SpectacularAPIView.as_view(), name='schema'),
    path('swagger', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
>>>>>>> Stashed changes
]
