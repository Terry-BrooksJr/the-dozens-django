"""Django app configuration for the GraphQL API."""

from django.apps import AppConfig


class GraphQlConfig(AppConfig):
    """AppConfig for ``applications.graphQL``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.graphQL"
