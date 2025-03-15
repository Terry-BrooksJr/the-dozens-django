# -*- coding: utf-8 -*-
from applications.graphQL.query import Query
from graphene import Schema

schema = Schema(query=Query)  # , mutation=Mutation, subscription=Subscription)
