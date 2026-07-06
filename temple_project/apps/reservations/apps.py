from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "temple_project.apps.reservations"
    verbose_name = "Réservations"

    def ready(self):
        from . import signals  # noqa: F401
