# -*- coding: utf-8 -*-
from django.urls import path
from graphene_django.views import GraphQLView

from applications.graphQL.schema import schema

urlpatterns = [
    path("", GraphQLView.as_view(graphiql=True, schema=schema)),
]
