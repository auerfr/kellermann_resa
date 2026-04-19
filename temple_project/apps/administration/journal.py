"""
Helper de traçabilité — appeler depuis n'importe quelle vue.

Usage minimal :
    from temple_project.apps.administration.journal import log_evenement
    log_evenement('validation_reservation', "Réservation validée", request=request, objet=resa)

Toutes les erreurs sont silencieuses : un bug de log ne doit jamais casser une vue.
"""
from __future__ import annotations

# Mapping classe modèle → objet_type string
# Rempli à l'exécution (lazy) pour éviter les imports circulaires au chargement.
_OBJET_TYPE_MAP: dict = {}


def _get_objet_type_map() -> dict:
    """Construit le mapping classe → objet_type au premier appel."""
    global _OBJET_TYPE_MAP
    if _OBJET_TYPE_MAP:
        return _OBJET_TYPE_MAP
    try:
        from temple_project.apps.reservations.models import (
            Reservation, ReservationSalle, ValidationSaison,
        )
        from temple_project.apps.loges.models import Loge
        _OBJET_TYPE_MAP = {
            Reservation:       'reservation',
            ReservationSalle:  'reservation_salle',
            Loge:              'loge',
            ValidationSaison:  'validation_saison',
        }
    except Exception:
        pass
    return _OBJET_TYPE_MAP


def _extract_ip(request) -> str | None:
    """Retourne l'IP réelle du client, en gérant les proxys (PythonAnywhere)."""
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def log_evenement(
    type_evenement: str,
    description: str,
    *,
    request=None,
    utilisateur=None,
    objet=None,
    objet_type: str = '',
    objet_label: str = '',
) -> object | None:
    """
    Crée un JournalEvenement.

    Paramètres
    ----------
    type_evenement : str
        Une des clés de JournalEvenement.TYPE_CHOICES.
    description : str
        Texte libre décrivant l'action.
    request : HttpRequest, optionnel
        Utilisé pour extraire l'utilisateur connecté et l'IP.
    utilisateur : User, optionnel
        Surcharge request.user si fourni explicitement.
    objet : instance de modèle Django, optionnel
        Si fourni, objet_id, objet_type et objet_label sont déduits automatiquement.
    objet_type : str, optionnel
        Surcharge la déduction depuis `objet`.
    objet_label : str, optionnel
        Surcharge str(objet).

    Retourne l'instance créée, ou None si une erreur survient.
    """
    try:
        from .models import JournalEvenement

        # ── Utilisateur ──────────────────────────────────────────────────────
        user = utilisateur
        if user is None and request is not None:
            u = getattr(request, 'user', None)
            if u is not None and u.is_authenticated:
                user = u

        # ── IP ───────────────────────────────────────────────────────────────
        ip = _extract_ip(request)

        # ── Objet ────────────────────────────────────────────────────────────
        obj_id    = None
        obj_type  = objet_type
        obj_label = objet_label

        if objet is not None:
            obj_id = getattr(objet, 'pk', None)
            if not obj_label:
                obj_label = str(objet)[:300]
            if not obj_type:
                obj_type = _get_objet_type_map().get(type(objet), 'systeme')

        return JournalEvenement.objects.create(
            type_evenement=type_evenement,
            description=description,
            utilisateur=user,
            objet_type=obj_type,
            objet_id=obj_id,
            objet_label=obj_label,
            ip_address=ip,
        )

    except Exception:
        # Ne jamais faire crasher la vue appelante
        import logging
        logging.getLogger(__name__).exception(
            "log_evenement a échoué pour type=%s", type_evenement
        )
        return None
