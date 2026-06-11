from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin


def _fmt_heure(t):
    return t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5]


def envoyer_email_nouvelle_demande(resa):
    """Appele depuis la vue reservations quand une nouvelle demande arrive."""
    sujet = f"[Kellermann] Nouvelle demande - {resa.loge} le {resa.date:%d/%m/%Y}"
    corps = f"""Nouvelle demande recue.

  Loge      : {resa.loge}
  Temple    : {resa.temple}
  Date      : {resa.date:%d/%m/%Y}
  Horaires  : {_fmt_heure(resa.heure_debut)} - {_fmt_heure(resa.heure_fin)}
  Demandeur : {resa.nom_demandeur} ({resa.email_demandeur})

Connectez-vous pour traiter cette demande.
"""
    try:
        send_mail_kellermann(sujet, corps, [get_email_admin()])
    except Exception:
        pass