"""Django app configuration for the ``core`` project package."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """AppConfig for ``core``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
