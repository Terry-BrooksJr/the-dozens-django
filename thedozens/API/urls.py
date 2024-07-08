# -*- coding: utf-8 -*-
from API import views
from django.urls import path
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)

urlpatterns = [
    path("insults/<str:category>", views.InsultsView.as_view(), name="List_View"),
    path("insult/<int:id>", views.InsultSingleItem.as_view(), name="Single_View"),
    # path("insult", views.randomUnfilteredInsult, name="Random-Unfiltered"),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
]
