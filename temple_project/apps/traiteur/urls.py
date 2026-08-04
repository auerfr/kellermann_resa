from django.urls import path
from . import views

app_name = "traiteur"

urlpatterns = [
    # ── Espace traiteur (groupe requis) ──
    path("",                     views.tableau_de_bord,          name="tableau_de_bord"),
    path("calendrier/",          views.calendrier,               name="calendrier"),
    path("planning/",            views.planning,                 name="planning"),
    path("reserver/",            views.reserver,                 name="reserver"),
    path("loges-couverts/",      views.loges_couverts,           name="loges_couverts"),
    path("bloquer/",             views.bloquer,                  name="bloquer"),
    path("bloquer/<int:pk>/supprimer/", views.supprimer_blocage, name="supprimer_blocage"),
    path("notification/<int:pk>/lu/",   views.marquer_notification_lue, name="marquer_notification_lue"),
    path("export-agapes/",       views.export_agapes_excel,      name="export_agapes_excel"),
    path("etat-des-lieux/",      views.etat_des_lieux,           name="etat_des_lieux"),
    path("guide/",               views.guide_traiteur,           name="guide"),

    # ── Accessible aux membres (cookie) ──
    path("notification/",             views.notification,           name="notification"),
    path("notification/confirmation/", views.notification_confirmee, name="notification_confirmee"),
]
