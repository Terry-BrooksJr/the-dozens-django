# -*- coding: utf-8 -*-
from applications.graphQL.schema import schema
from django.urls import path
from graphene_django.views import GraphQLView

urlpatterns = [
    path("", GraphQLView.as_view(graphiql=True, schema=schema)),
]
