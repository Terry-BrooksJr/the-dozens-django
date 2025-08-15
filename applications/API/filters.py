"""
module: applications.API.filters

"""

from applications.API.models import Insult
from django_filters import rest_framework as filters


class InsultFilter(filters.FilterSet):
    """
    Provides filtering options for Insult objects in the API.

    This filter allows users to filter insults by their NSFW status and category.
    """

    class Meta:
        model = Insult
        fields = {
            "nsfw": ["exact"],
            "category": ["exact"],
        }


class MyInsultFilter(filters.FilterSet):
    """
    Provides filtering options for user-submitted Insult objects in the API.

    This filter enables filtering insults by NSFW status, category, and status fields.
    """

    class Meta:
        model = Insult
        fields = {"nsfw": ["exact"], "category": ["exact"], "status": ["exact"]}
