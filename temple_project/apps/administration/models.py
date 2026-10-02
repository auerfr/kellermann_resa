from datetime import date
from decimal import Decimal
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

    # ── Facturation ───────────────────────────────────────────────────────────
    facturation_active = models.BooleanField(
        default=True,
        help_text="Active la facturation des occupations. À désactiver tant que "
                  "le modèle n'est pas validé avec le trésorier.")
    # Tarifs récurrents par membre (base à confirmer avec le trésorier)
    tarif_membre_loge = models.DecimalField(
        max_digits=8, decimal_places=2, default=85,
        help_text="Redevance par membre pour une loge bleue (€).")
    tarif_membre_hg = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('22.80'),
        help_text="Redevance par membre pour un haut grade (€).")
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
    tarif_funebre = models.DecimalField(
        max_digits=8, decimal_places=2, default=100,
        help_text="Tenue funèbre exceptionnelle (week-end / vacances) (€)")
    # ── Tarifs occupants externes / occasionnels ──────────────────────────────
    tarif_loge_occasionnelle = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('150'),
        help_text="Loge externe ou occasionnelle (invitée, de passage), par tenue (€)")
    tarif_hg_externe = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('100'),
        help_text="Atelier haut grade externe / inter-obédientiel, par tenue (€)")
    tarif_hg_interne_non_regulier = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('50'),
        help_text="Atelier HG interne non régulier (2-3 tenues/an, pas de règle récurrente), par tenue (€)")
    tarif_date_effet = models.DateField(
        null=True, blank=True, default=date(2026, 6, 12),
        help_text="Date d'entrée en vigueur des tarifs (vote AG). Les occupations "
                  "antérieures ne sont pas facturées.")
    # ── Module finance (facturation annuelle par loge) ────────────────────────
    module_finance_actif = models.BooleanField(
        default=False,
        help_text="Active le module de facturation annuelle par loge "
                  "(factures cristallisées, PDF, envoi email). "
                  "À activer après validation du modèle avec le trésorier.")
    # Effectif par défaut quand la fiche loge n'est pas encore renseignée
    effectif_par_defaut = models.PositiveSmallIntegerField(
        default=25,
        help_text="Effectif utilisé (en estimation) pour le calcul des cotisations "
                  "quand la fiche loge n'a pas encore d'effectif saisi.")
    # Lien vers le schéma de tarification actuellement actif (nullable, compatibilité)
    schema_actif = models.ForeignKey(
        'SchemaTarification', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text="Schéma de tarification voté en AG et actuellement en vigueur."
    )

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

class PosteCharge(models.Model):
    """Poste de charge d'infrastructure pour simulation budgétaire."""
    TYPE_CHOICES = [
        ('fixe',      'Charge fixe (loyer, assurance, maintenance…)'),
        ('mutualise', 'Variable mutualisée (chauffage, électricité de base…)'),
        ('marginal',  'Variable marginale (nettoyage, consommables…)'),
        ('agapes',    'Usage cuisine / agapes (uniquement si agapes demandées)'),
        ('salle',     'Salle de réunion / cabinet (par occupation de salle)'),
    ]
    UNITE_CHOICES = [
        ('annuel',        'Par an'),
        ('mensuel',       'Par mois'),
        ('par_heure',     'Par heure d\'occupation'),
        ('par_evenement', 'Par événement'),
    ]
    temple = models.ForeignKey(
        'reservations.Temple', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='postes_charges',
        help_text="Laisser vide pour un poste commun à tous les temples",
    )
    saison    = models.PositiveIntegerField(help_text="Année de début de saison (ex : 2025 pour 2025-2026)")
    libelle   = models.CharField(max_length=100)
    type_charge = models.CharField(max_length=20, choices=TYPE_CHOICES)
    montant   = models.DecimalField(max_digits=10, decimal_places=2)
    unite     = models.CharField(max_length=20, choices=UNITE_CHOICES)
    actif     = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Poste de charge"
        verbose_name_plural = "Postes de charges"
        ordering            = ['saison', 'temple', 'type_charge', 'libelle']

    def __str__(self):
        return f"{self.libelle} ({self.get_type_charge_display()}, {self.montant} € / {self.get_unite_display()})"

    @property
    def montant_annuel_normalise(self):
        """Pour les postes fixes : ramène à une valeur annuelle."""
        from decimal import Decimal
        if self.unite == 'annuel':
            return self.montant
        if self.unite == 'mensuel':
            return self.montant * Decimal('12')
        return Decimal('0')


class FAQ(models.Model):
    """Entrée de FAQ — gérable par l'admin sans toucher au code."""
    CATEGORIE_CHOICES = [
        ('connexion', 'Page de connexion (mini FAQ)'),
        ('membres',   'FAQ membres connectés'),
        ('traiteur',  'FAQ traiteur'),
    ]
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, db_index=True)
    section   = models.CharField(max_length=100, blank=True,
                                  help_text="Titre de section (ex: Réservations, Calendrier…)")
    question  = models.CharField(max_length=400)
    reponse   = models.TextField()
    ordre     = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage dans la catégorie")
    actif     = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "FAQ"
        verbose_name_plural = "FAQ"
        ordering = ['categorie', 'ordre', 'pk']

    def __str__(self):
        return f"[{self.get_categorie_display()}] {self.question[:60]}"


# ── Module Finance — Schémas de tarification & Décisions d'AG ────────────────

class SchemaTarification(models.Model):
    """Schéma de tarification versionné, lié ou non à une décision d'AG."""
    MODES = [
        ('membre',  'Par membre'),
        ('hybride', 'Hybride (membre + tenue)'),
    ]
    STATUTS = [
        ('simule', 'Simulé'),
        ('vote',   'Voté en AG'),
    ]

    nom          = models.CharField(max_length=200)
    saison       = models.PositiveSmallIntegerField(help_text="Année de début de saison (ex : 2026 pour 2026-2027)")
    date_effet   = models.DateField(null=True, blank=True)
    statut       = models.CharField(max_length=10, choices=STATUTS, default='simule')
    mode         = models.CharField(max_length=10, choices=MODES, default='membre')

    # Tarifs cotisation annuelle
    tarif_membre_loge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    tarif_membre_hg   = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    # Tarifs part tenue (mode hybride)
    tarif_tenue_lb    = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    tarif_tenue_hg    = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    # Tarifs tenues exceptionnelles
    tarif_exc_sans_agapes = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    tarif_exc_avec_agapes = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    tarif_congres_jour    = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    tarif_funebre         = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    # Contraintes optionnelles
    tarif_minimum      = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                             help_text="Minimum de cotisation par structure (€, optionnel)")
    plafond_hausse_pct = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True,
                                             help_text="Plafond de hausse par rapport au tarif précédent (%)")
    notes    = models.TextField(blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='schemas_crees')
    cree_le    = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Schéma de tarification"
        verbose_name_plural = "Schémas de tarification"
        ordering = ['-saison', '-cree_le']

    def __str__(self):
        return f"{self.nom} ({self.saison}-{self.saison + 1}) [{self.get_statut_display()}]"


POSTES_BUDGET = [
    ('budget_energie',       'Énergie (électricité, gaz)'),
    ('budget_fluides',       'Eau et fluides'),
    ('budget_consommables',  'Consommables et petits équipements'),
    ('budget_entretien',     'Entretien et réparations'),
    ('budget_maintenance',   'Maintenance et contrôles réglementaires'),
    ('budget_assurances',    'Assurances'),
    ('budget_services_ext',  'Autres services extérieurs (dont nettoyage)'),
    ('budget_impots',        'Impôts et taxes'),
    ('budget_personnel',     'Frais de personnel'),
    ('budget_amortissements','Dotation aux amortissements'),
]


class DecisionAG(models.Model):
    """Décision d'Assemblée Générale : budget voté + schéma de tarification voté."""
    STATUTS = [
        ('brouillon', 'Brouillon'),
        ('votee',     'Votée'),
    ]

    saison              = models.PositiveSmallIntegerField(help_text="Saison concernée (ex : 2026 pour 2026-2027)")
    date_ag             = models.DateField()
    libelle_resolution  = models.CharField(max_length=500, help_text="Titre ou numéro de résolution")
    pv                  = models.FileField(upload_to='pv_ag/', null=True, blank=True,
                                           help_text="Procès-verbal de l'AG (PDF)")
    statut              = models.CharField(max_length=10, choices=STATUTS, default='brouillon')
    schema              = models.ForeignKey(SchemaTarification, null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name='decisions_ag')

    # Budget voté par poste (nomenclature comptable)
    budget_energie       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_fluides       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_consommables  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_entretien     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_maintenance   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_assurances    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_services_ext  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_impots        = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_personnel     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    budget_amortissements= models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    notes    = models.TextField(blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='decisions_ag_creees')
    cree_le    = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    @property
    def budget_total(self):
        return sum(getattr(self, champ) for champ, _ in POSTES_BUDGET)

    class Meta:
        verbose_name        = "Décision d'AG"
        verbose_name_plural = "Décisions d'AG"
        ordering = ['-saison', '-date_ag']

    def __str__(self):
        return f"AG {self.date_ag.strftime('%d/%m/%Y')} — {self.libelle_resolution[:60]}"


# ── Module Finance — Facturation annuelle par loge ────────────────────────────

class Facture(models.Model):
    """Facture annuelle cristallisée pour une loge, sur une saison."""
    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('emise',     'Émise'),
        ('payee',     'Payée'),
        ('annulee',   'Annulée'),
    ]
    loge          = models.ForeignKey(
        'loges.Loge', on_delete=models.PROTECT, related_name='factures')
    saison        = models.PositiveIntegerField(
        help_text="Année de début de saison (ex : 2025 pour 2025-2026)")
    numero        = models.CharField(max_length=30, blank=True, db_index=True,
                                     help_text="Numéro définitif généré à l'émission (ex: KELL-2026-001)")
    date_emission = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    statut        = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon', db_index=True)
    notes            = models.TextField(blank=True, help_text="Notes libres (exonération partielle, accord trésorier…)")
    total_ht         = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    schema_applique  = models.ForeignKey(
        'SchemaTarification', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='factures',
        help_text="Schéma de tarification utilisé pour générer cette facture"
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Facture"
        verbose_name_plural = "Factures"
        ordering            = ['-saison', 'loge__nom']
        constraints = [
            models.UniqueConstraint(fields=['loge', 'saison'], name='finance_facture_loge_saison_uniq'),
        ]
        indexes = [
            models.Index(fields=['-saison', 'statut'], name='finance_facture_saison_idx'),
        ]

    def __str__(self):
        num = self.numero or 'Brouillon'
        return f"{num} — {self.loge} ({self.saison}-{self.saison + 1})"

    def recalculer_total(self):
        from decimal import Decimal as D
        self.total_ht = sum(
            (l.montant_total for l in self.lignes.filter(facturable=True)),
            D('0')
        )
        self.save(update_fields=['total_ht', 'updated_at'])


class LigneFacture(models.Model):
    """Ligne d'une facture annuelle (cotisations, tenues, agapes, salle…)."""
    TYPE_CHOICES = [
        ('cotisation_lb',        'Cotisation membre — loge bleue'),
        ('cotisation_hg',        'Cotisation membre — haut grade'),
        ('infrastructure_fixe',  'Part infrastructure fixe'),
        ('infrastructure_mut',   'Part infrastructure mutualisée'),
        ('infrastructure_marg',  'Part infrastructure marginale'),
        ('agapes',               'Usage cuisine / agapes'),
        ('salle',                'Usage salle de réunion'),
        ('tenue_exc',            'Tenue exceptionnelle'),
        ('autre',                'Autre'),
    ]
    facture           = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name='lignes')
    type_ligne        = models.CharField(max_length=30, choices=TYPE_CHOICES)
    libelle           = models.CharField(max_length=200)
    quantite          = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1'))
    unite             = models.CharField(max_length=50, blank=True)
    montant_unitaire  = models.DecimalField(max_digits=10, decimal_places=2)
    montant_total     = models.DecimalField(max_digits=10, decimal_places=2)
    facturable        = models.BooleanField(default=True,
                                            help_text="Décocher pour exclure cette ligne sans la supprimer")
    reservation       = models.ForeignKey(
        'reservations.Reservation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lignes_facture')
    reservation_salle = models.ForeignKey(
        'reservations.ReservationSalle', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lignes_facture')
    ordre             = models.PositiveIntegerField(default=0)
    # Correction manuelle : motif enregistré pour l'audit
    note_override     = models.CharField(max_length=300, blank=True,
                                         help_text="Motif de la correction manuelle du tarif (ex: cuisine partagée)")

    class Meta:
        verbose_name        = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering            = ['ordre', 'type_ligne']

    def __str__(self):
        return f"{self.libelle} ({self.montant_total} €)"
