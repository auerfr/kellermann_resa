from django.apps import AppConfig


class AuthCustomConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "temple_project.apps.auth_custom"
    verbose_name = "Authentification"
