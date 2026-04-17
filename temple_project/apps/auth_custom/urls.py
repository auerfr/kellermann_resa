from django.urls import path
from . import views

app_name = "acces"

urlpatterns = [
    path("",          views.bienvenue,       name="bienvenue"),
    path("login/",    views.login_visiteur,  name="login_visiteur"),
    path("admin/",    views.login_admin,     name="login_admin"),
    path("traiteur/", views.login_traiteur,  name="login_traiteur"),
    path("logout/",   views.deconnexion,     name="deconnexion"),
]
