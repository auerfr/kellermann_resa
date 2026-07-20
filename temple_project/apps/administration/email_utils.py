from django.core.mail import send_mail as django_send_mail, get_connection
from django.conf import settings


def _load_params():
    try:
        from temple_project.apps.administration.models import Parametres
        return Parametres.objects.first()
    except Exception:
        return None


def get_email_connection():
    """Retourne un EmailBackend configuré depuis Parametres, sinon le backend Django par défaut."""
    params = _load_params()
    if params and params.smtp_host:
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=params.smtp_host,
            port=params.smtp_port,
            username=params.smtp_user,
            password=params.smtp_password,
            use_tls=params.smtp_tls,
            fail_silently=False,
        )
    return get_connection()


def get_email_admin():
    """Retourne l'email admin depuis Parametres, sinon DEFAULT_FROM_EMAIL."""
    params = _load_params()
    if params and params.email_admin:
        return params.email_admin
    return settings.DEFAULT_FROM_EMAIL


def get_email_traiteur():
    """Retourne l'email traiteur si configuré, sinon None."""
    params = _load_params()
    if params and params.email_traiteur:
        return params.email_traiteur
    return None


# Adresse du formulaire de contact « message libre » (adaptez le domaine si besoin).
CONTACT_FORM_URL = "https://kellermanadmin.eu.pythonanywhere.com/reservations/contact/"

NOREPLY_FOOTER = (
    "\n\n"
    "— — —\n"
    "Cet email est envoyé automatiquement depuis une adresse non surveillée : "
    "merci de ne pas y répondre.\n"
    "Pour toute question ou demande, utilisez exclusivement le formulaire de contact du site "
    "(« Message libre ») :\n"
    f"{CONTACT_FORM_URL}"
)

NOREPLY_FOOTER_HTML = (
    '<hr style="border:none;border-top:1px solid #E2E8F0;margin:20px 0;">'
    '<p style="font-size:12px;color:#64748B;line-height:1.5;">'
    'Cet email est envoyé automatiquement depuis une adresse non surveillée : '
    '<strong>merci de ne pas y répondre</strong>.<br>'
    'Pour toute question ou demande, utilisez exclusivement le formulaire de contact du site '
    f'(« Message libre ») : <a href="{CONTACT_FORM_URL}">{CONTACT_FORM_URL}</a>'
    '</p>'
)


def send_mail_kellermann(subject, message, recipient_list, fail_silently=True, html_message=None):
    """Envoie un email via la configuration SMTP de Parametres.

    Ajoute automatiquement un nom d'expéditeur « (ne pas répondre) » et un pied de page
    invitant à passer par le formulaire de contact, l'adresse Gmail servant de noreply."""
    params = _load_params()
    from_email = (
        params.email_from
        if params and params.email_from
        else settings.DEFAULT_FROM_EMAIL
    )
    # Nom d'expéditeur explicite « ne pas répondre » (si pas déjà formaté « Nom <email> »)
    if from_email and '<' not in from_email:
        from_email = f"Kellermann Réservations (ne pas répondre) <{from_email}>"

    message = (message or '') + NOREPLY_FOOTER
    if html_message:
        html_message = html_message + NOREPLY_FOOTER_HTML

    connection = get_email_connection()
    django_send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        connection=connection,
        fail_silently=fail_silently,
        html_message=html_message,
    )
