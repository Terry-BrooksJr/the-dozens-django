from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications.API"
    
    def ready(self):
        from applications.API import schema_extenstions #noqa
