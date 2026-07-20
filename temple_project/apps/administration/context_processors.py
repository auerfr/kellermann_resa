from django.db.models import Q
from django.utils import timezone

from .models import Annonce


def annonce_active(request):
    """Injecte l'annonce pop-up active (si une fenêtre de diffusion est en cours)."""
    # Pas de pop-up dans l'admin Django
    if request.path.startswith('/django-admin'):
        return {}
    try:
        now = timezone.now()
        annonce = (
            Annonce.objects
            .filter(actif=True)
            .filter(Q(date_debut__isnull=True) | Q(date_debut__lte=now))
            .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=now))
            .order_by('-created_at')
            .first()
        )
    except Exception:
        # La table n'existe pas encore (avant migration) : ne rien casser
        annonce = None
    return {'annonce_popup': annonce}


def messagerie(request):
    """Nombre de messages non lus, pour le badge navbar (staff uniquement)."""
    try:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_staff:
            from temple_project.apps.reservations.models import MessageContact
            return {'nb_messages_nouveaux': MessageContact.objects.filter(statut='nouveau').count()}
    except Exception:
        pass
    return {'nb_messages_nouveaux': 0}
