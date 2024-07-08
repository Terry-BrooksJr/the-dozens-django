# -*- coding: utf-8 -*-
from API.models import Insult
from graphene import Argument, Enum, Mutation


class Mutation(Mutation):
    def mutate(root, info, **kwargs):
        pass

    # class JokeCategory(Enum):
    #     class Meta:
    #         enum = Insult.CATEGORY
    #         description = "Enumerated Catagory for Jokes"
    # class Arguments:
    #     category = Argument(Mutation.JokeCategory,required=True)
