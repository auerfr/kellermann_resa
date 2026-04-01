from django.urls import path
from . import views

app_name = "reservations"

urlpatterns = [
    # Temples
    path("demande/",
         views.soumettre_demande,
         name="demande"),
    path("confirmation/<uuid:uuid>/",
         views.confirmation,
         name="confirmation"),
    path("suivi/<uuid:uuid>/",
         views.suivi_reservation,
         name="suivi"),
    path("api/verifier-conflit/",
         views.api_verifier_conflit,
         name="api_verifier_conflit"),

    # Salles de réunion
    path("demande-salle/",
         views.soumettre_demande_salle,
         name="demande_salle"),
    path("confirmation-salle/<uuid:uuid>/",
         views.confirmation_salle,
         name="confirmation_salle"),
    path("suivi-salle/<uuid:uuid>/",
         views.suivi_salle,
         name="suivi_salle"),

    # Cabinets de réflexion
    path("cabinets/",
         views.demande_cabinets,
         name="demande_cabinets"),
    path("api/cabinets-disponibles/",
         views.api_cabinets_disponibles,
         name="api_cabinets_disponibles"),

    # Banquet d'ordre
    path("banquet/",
         views.demande_banquet,
         name="demande_banquet"),
    path("confirmation-banquet/<uuid:uuid>/",
         views.confirmation_banquet,
         name="confirmation_banquet"),

    # API
    path("api/verifier-conflit/",
         views.api_verifier_conflit,
         name="api_verifier_conflit"),
]
