from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from temple_project.apps.auth_custom.views import bienvenue

urlpatterns = [
    path("", bienvenue, name="accueil"),
    path("auth/", include("temple_project.apps.auth_custom.urls")),
    path("django-admin/", admin.site.urls),
    path("calendrier/",   include("temple_project.apps.calendrier.urls")),
    path("reservations/", include("temple_project.apps.reservations.urls")),
    path("loges/",        include("temple_project.apps.loges.urls")),
    path("exports/",      include("temple_project.apps.exports.urls")),
    path("admin/",        include("temple_project.apps.administration.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
