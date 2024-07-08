# -*- coding: utf-8 -*-
import random

from API.filters import InsultFilter
from API.models import Insult
from API.serializers import InsultsCategorySerializer, InsultSerializer
from django_filters import rest_framework as filters
from rest_framework import status
from rest_framework.decorators import (api_view, permission_classes,
                                       renderer_classes)
from rest_framework.generics import (ListAPIView, RetrieveAPIView,
                                     RetrieveUpdateDestroyAPIView)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response


class InsultMe(RetrieveAPIView):
    serializer_class = InsultSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        nsfw = None
        category = None

        queryset = queryset # TODO
        return queryset
class InsultsView(ListAPIView):
    queryset = Insult.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "category"
    serializer_class = InsultsCategorySerializer
    permission_classes = [AllowAny]


class InsultSingleItem(RetrieveAPIView):
    queryset = Insult.objects.all()
    lookup_field = "id"
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    serializer_class = InsultSerializer
    permission_classes = [AllowAny]

class MyInsultsView(RetrieveUpdateDestroyAPIView):
    serializer_class = InsultSerializer
    filterset_class = InsultFilter
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        """
        This view returns a list of all insults created by the currently
        authenticated user.

        Returns empty list if user Anonymous
        """
        user = self.request.user

        if not user.is_anonymous:
            return Insult.objects.filter(added_by=user)

        return Insult.objects.none()
