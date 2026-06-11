from django.conf import settings
from django.db import models


class Parametres(models.Model):
    mot_de_passe_annuel = models.CharField(max_length=100, default="KELLERMANN2026")
    email_admin    = models.EmailField()
    email_traiteur = models.EmailField(blank=True, help_text="Copie automatique pour le traiteur sur agapes/banquets")
    email_from     = models.EmailField(default="noreply@temple-reservations.fr")
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_tls = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Paramètres"
        verbose_name_plural = "Paramètres"

    @classmethod
    def get_instance(cls):
        instance, created = cls.objects.get_or_create(pk=1, defaults={})
        return instance


class JournalEvenement(models.Model):
    """Journal de traçabilité des actions importantes (admin uniquement)."""

    TYPE_CHOICES = [
        ('validation_reservation',       'Validation réservation'),
        ('refus_reservation',            'Refus réservation'),
        ('modification_reservation',     'Modification réservation'),
        ('soumission_portail_loge',      'Soumission portail loge'),
        ('ouverture_validation_saison',  'Ouverture validation saison'),
        ('envoi_emails_saison',          'Envoi emails saison'),
        ('soumission_validation_loge',   'Soumission validation loge'),
        ('import_excel',                 'Import Excel'),
        ('backup_base',                  'Backup base de données'),
        ('creation_reservation_directe', 'Création réservation directe'),
    ]

    OBJET_TYPE_CHOICES = [
        ('reservation',       'Réservation'),
        ('reservation_salle', 'Réservation salle'),
        ('loge',              'Loge'),
        ('validation_saison', 'Validation de saison'),
        ('systeme',           'Système'),
    ]

    date_heure     = models.DateTimeField(auto_now_add=True, db_index=True)
    utilisateur    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='evenements_journal',
    )
    type_evenement = models.CharField(max_length=40, choices=TYPE_CHOICES, db_index=True)
    description    = models.TextField()
    objet_type     = models.CharField(max_length=30, choices=OBJET_TYPE_CHOICES, blank=True)
    objet_id       = models.PositiveIntegerField(null=True, blank=True)
    objet_label    = models.CharField(max_length=300, blank=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name          = "Événement journal"
        verbose_name_plural   = "Journal des événements"
        ordering              = ['-date_heure']
        indexes = [
            models.Index(fields=['-date_heure']),
            models.Index(fields=['type_evenement']),
            models.Index(fields=['objet_type', 'objet_id']),
        ]

    def __str__(self):
        user = self.utilisateur.username if self.utilisateur else 'système'
        return f"[{self.get_type_evenement_display()}] {user} – {self.date_heure:%d/%m/%Y %H:%M}"