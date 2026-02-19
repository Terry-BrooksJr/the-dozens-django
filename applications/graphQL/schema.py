# -*- coding: utf-8 -*-
from graphene import Schema

from applications.graphQL.query import Query

schema = Schema(query=Query)  # , mutation=Mutation, subscription=Subscription)
