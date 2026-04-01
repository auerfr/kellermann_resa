from django.urls import path
from . import views

app_name = "calendrier"

urlpatterns = [
    path("",                    views.calendrier_principal, name="principal"),
    path("api/evenements/",     views.api_evenements,       name="api_evenements"),
    path("api/disponibilites/", views.api_disponibilites,   name="api_disponibilites"),
]
