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


def send_mail_kellermann(subject, message, recipient_list, fail_silently=True, html_message=None):
    """Envoie un email via la configuration SMTP de Parametres."""
    params = _load_params()
    from_email = (
        params.email_from
        if params and params.email_from
        else settings.DEFAULT_FROM_EMAIL
    )
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
