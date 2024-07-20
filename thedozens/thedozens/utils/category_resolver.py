from API.models import Insult
from typing import Dict
class Resolver():
    @classmethod
    def _generate_insult_category_dict(cls) -> Dict[str, str]:
        # sourcery skip: collection-builtin-to-comprehension, identity-comprehension
        insult_tuples = Insult.CATEGORY.choices
        return dict((x, y) for x, y in insult_tuples)
    @staticmethod
    def resolve(category_selection: str) -> str:
        """
            Resolves the given insult category selection to its corresponding category.
            
            Args:
                category_selection: A string representing the selected insult category.
                
            Returns:
                A string representing the resolved insult category.
                
            Raises:
                ValueError: If the provided category_selection is not a valid Insult Category.
        """
        category_selection = category_selection.lower()
        insult_category_dict = Resolver._generate_insult_category_dict()

        if (
            category_selection not in insult_category_dict.keys()
            or category_selection not in insult_category_dict.items()
        ):
            raise ValueError(f"{category_selection} is not a valid Insult Category")

        for key, value in insult_category_dict.items():
            if category_selection == key:
                return category_selection
            elif category_selection == value:
                return key
            else:
                continue