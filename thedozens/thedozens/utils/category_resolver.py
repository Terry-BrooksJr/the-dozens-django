from API.models import Insult
from typing import Dict
from loguru import logger
from prometheus_client import Histogram

class Resolver:
    cat_resolver_metric= Histogram("category_resolver", "Metric of the Duration of categories in request")

    @classmethod
    def _generate_insult_category_dict(cls) -> Dict[str, str]:
        insult_tuples = Insult.CATEGORY.choices
        return dict(insult_tuples)
    
    # @cat_resolver_metric.time()
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
        reverse_insult_category_dict = {v: k for k, v in insult_category_dict.items()}

        if category_selection in insult_category_dict:
            return category_selection
        elif category_selection in reverse_insult_category_dict:
            return reverse_insult_category_dict[category_selection]
        else:
            logger.error(f'ERROR: Unable to Resolve {category_selection}')
            raise ValueError(f"{category_selection} is not a valid Insult Category")
