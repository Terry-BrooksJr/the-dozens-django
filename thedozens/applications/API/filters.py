# -*- coding: utf-8 -*-
from applications.API.models import Insult
from django_filters import rest_framework as filters


class InsultFilter(filters.FilterSet):
    class Meta:
        model = Insult
        fields = {
            "nsfw": ["exact"],
            "category": ["exact"],
        }


class MyInsultFilter(filters.FilterSet):
    class Meta:
        model = Insult
        fields = {"nsfw": ["exact"], "category": ["exact"], "status": ["exact"]}
