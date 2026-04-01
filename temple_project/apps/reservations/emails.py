from django.core.mail import send_mail
from django.conf import settings


def envoyer_email_nouvelle_demande(resa):
    """Appele depuis la vue reservations quand une nouvelle demande arrive."""
    sujet = f"[Kellermann] Nouvelle demande - {resa.loge} le {resa.date:%d/%m/%Y}"
    corps = f"""Nouvelle demande recue.

  Loge      : {resa.loge}
  Temple    : {resa.temple}
  Date      : {resa.date:%d/%m/%Y}
  Horaires  : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
  Demandeur : {resa.nom_demandeur} ({resa.email_demandeur})

Connectez-vous pour traiter cette demande.
"""
    try:
        send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL], fail_silently=True)
    except Exception:
        pass