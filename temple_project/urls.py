from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from temple_project.apps.auth_custom.views import bienvenue


def _ics_global(request):
    from temple_project.apps.reservations.views import ics_global
    return ics_global(request)


def _portail_loge_ics(request, token):
    from temple_project.apps.reservations.views import portail_loge_ics
    return portail_loge_ics(request, token)


def _faq_membres(request):
    from temple_project.apps.administration.views import faq_membres
    return faq_membres(request)


def _faq_traiteur(request):
    from temple_project.apps.administration.views import faq_traiteur
    return faq_traiteur(request)


handler404 = 'temple_project.views.error_404'
handler500 = 'temple_project.views.error_500'
handler403 = 'temple_project.views.error_403'

urlpatterns = [
    path("", bienvenue, name="accueil"),
    path("auth/", include("temple_project.apps.auth_custom.urls")),
    path("django-admin/", admin.site.urls),
    path("calendrier/",   include("temple_project.apps.calendrier.urls")),
    path("reservations/", include("temple_project.apps.reservations.urls")),
    path("loges/",        include("temple_project.apps.loges.urls")),
    path("exports/",      include("temple_project.apps.exports.urls")),
    path("admin/",        include("temple_project.apps.administration.urls")),
    path("traiteur/",     include("temple_project.apps.traiteur.urls")),
    path("ics/global/",            _ics_global,         name="ics_global"),
    path("ics/loge/<uuid:token>/", _portail_loge_ics,   name="portail_loge_ics"),
    path("faq/membres/",           _faq_membres,         name="faq_membres"),
    path("faq/traiteur/",          _faq_traiteur,        name="faq_traiteur"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
