# -*- coding: utf-8 -*-
from API.models import Insult, InsultReview
from rest_framework import serializers


class InsultSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    NSFW = serializers.BooleanField(source="explicit")

    class Meta:
        model = Insult
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data[
            "added_by"
        ] = f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "

        return data


class InsultsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Insult
        fields = ("id", "content")


class MyInsultSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    NSFW = serializers.BooleanField(source="explicit")

    class Meta:
        model = Insult
        fields = "__all__"

class JokeReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsultReview
        fields = "__all__"