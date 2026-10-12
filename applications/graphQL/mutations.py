# from API.models import Insult
"""GraphQL mutations (placeholder; no mutations are implemented yet)."""

from graphene import Mutation  # , Argument, Enum


class Mutate(Mutation):
    """Placeholder base mutation."""

    def mutate(self, info, **kwargs):
        """No-op resolver; mutations are not yet supported."""

    # class JokeCategory(Enum):
    #     class Meta:
    #         enum = Insult.CATEGORY
    #         description = "Enumerated Catagory for Jokes"
    # class Arguments:
    #     category = Argument(Mutation.JokeCategory,required=True)
