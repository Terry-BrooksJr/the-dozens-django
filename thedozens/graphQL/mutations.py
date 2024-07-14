# from API.models import Insult
from graphene import Mutation  # , Argument, Enum


class Mutate(Mutation):
    def mutate(root, info, **kwargs):
        pass

    # class JokeCategory(Enum):
    #     class Meta:
    #         enum = Insult.CATEGORY
    #         description = "Enumerated Catagory for Jokes"
    # class Arguments:
    #     category = Argument(Mutation.JokeCategory,required=True)
