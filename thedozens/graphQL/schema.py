# -*- coding: utf-8 -*-
from graphene import Schema
from graphQL.mutations import Mutation
from graphQL.query import Query
from graphQL.subscriptions import Subscription

schema = Schema(query=Query)  # , mutation=Mutation, subscription=Subscription)
