from django.conf import settings
from django.db import models
from django.utils import timezone


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

    # ── Tarifs de facturation des réservations exceptionnelles ────────────────
    tarif_exc_sans_agapes = models.DecimalField(
        max_digits=8, decimal_places=2, default=100,
        help_text="Occupation exceptionnelle sans agapes (€)")
    tarif_exc_avec_agapes = models.DecimalField(
        max_digits=8, decimal_places=2, default=200,
        help_text="Occupation exceptionnelle avec agapes (€)")
    tarif_congres_jour = models.DecimalField(
        max_digits=8, decimal_places=2, default=300,
        help_text="Congrès / session régionale, par jour (€)")

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
        ('creation_acces_portail',       'Création accès portail'),
        ('envoi_lien_portail',           'Envoi lien portail'),
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
            models.Index(fields=['-date_heure'],          name='admin_journal_date_idx'),
            models.Index(fields=['type_evenement'],        name='admin_journal_type_idx'),
            models.Index(fields=['objet_type', 'objet_id'], name='admin_journal_objet_idx'),
        ]

    def __str__(self):
        user = self.utilisateur.username if self.utilisateur else 'système'
        return f"[{self.get_type_evenement_display()}] {user} – {self.date_heure:%d/%m/%Y %H:%M}"


class Annonce(models.Model):
    """Pop-up d'information configurable, affiché aux visiteurs pendant une fenêtre de diffusion."""

    NIVEAU_CHOICES = [
        ('info',    'Information (bleu)'),
        ('success', 'Succès (vert)'),
        ('warning', 'Avertissement (orange)'),
        ('danger',  'Important (rouge)'),
    ]

    titre           = models.CharField(max_length=200)
    message         = models.TextField(
        help_text="Texte affiché dans le pop-up. Les retours à la ligne sont conservés."
    )
    niveau          = models.CharField(max_length=10, choices=NIVEAU_CHOICES, default='info')
    actif           = models.BooleanField(default=True)
    date_debut      = models.DateTimeField(
        null=True, blank=True,
        help_text="Début de diffusion (laisser vide = immédiat)"
    )
    date_fin        = models.DateTimeField(
        null=True, blank=True,
        help_text="Fin de diffusion (laisser vide = sans limite)"
    )
    duree_affichage = models.PositiveIntegerField(
        default=0,
        help_text="Fermeture automatique après X secondes (0 = jusqu'à fermeture manuelle)"
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Annonce / Pop-up"
        verbose_name_plural = "Annonces / Pop-ups"
        ordering = ['-created_at']

    def __str__(self):
        return self.titre

    def est_active(self, maintenant=None):
        if not self.actif:
            return False
        maintenant = maintenant or timezone.now()
        if self.date_debut and maintenant < self.date_debut:
            return False
        if self.date_fin and maintenant > self.date_fin:
            return False
        return True

    def statut(self):
        if not self.actif:
            return 'inactive'
        now = timezone.now()
        if self.date_debut and now < self.date_debut:
            return 'programmee'
        if self.date_fin and now > self.date_fin:
            return 'expiree'
        return 'active'

    @property
    def version(self):
        """Identifiant de version pour le sessionStorage (change à chaque modification)."""
        return int(self.updated_at.timestamp()) if self.updated_at else 0