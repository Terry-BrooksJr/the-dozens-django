# -*- coding: utf-8 -*-
"""
module: applications.graphQL.schema

GraphQL schema assembly for the Insults API.

Composes the root Query type into the executable Graphene Schema that is
consumed by GraphQLView. The schema instance declared here is referenced
by both the URL configuration (applications.graphQL.urls) and the
GRAPHENE["SCHEMA"] setting in core.settings.

Mutations and subscriptions are reserved for future implementation;
their commented-out placeholders are intentional.
"""

from graphene import Schema

from applications.graphQL.query import Query

schema = Schema(query=Query)  # , mutation=Mutation, subscription=Subscription)
