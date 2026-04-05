import uuid
from django.db import models
from temple_project.apps.loges.models import Loge


class Temple(models.Model):
    NOM_CHOICES = [
        ("lafayette",  "Temple Lafayette"),
        ("liberte",    "Temple Liberté"),
        ("egalite",    "Temple Égalité"),
        ("fraternite", "Temple Fraternité"),
    ]
    nom       = models.CharField(max_length=50, choices=NOM_CHOICES, unique=True)
    description = models.TextField(blank=True)
    capacite  = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Temple"
        verbose_name_plural = "Temples"

    def __str__(self):
        return self.get_nom_display()


class Cabinet(models.Model):
    nom    = models.CharField(max_length=50)
    numero = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        verbose_name = "Cabinet de réflexion"
        verbose_name_plural = "Cabinets de réflexion"
        ordering = ["numero"]

    def __str__(self):
        return f"Cabinet {self.numero} – {self.nom}"


class SalleReunion(models.Model):
    TYPE_CHOICES = [
        ("reunion", "Réunion"),
        ("cabinet_reflexion", "Cabinet de réflexion"),
        ("agapes", "Agapes"),
    ]

    nom         = models.CharField(max_length=100)
    type_salle  = models.CharField(max_length=20, choices=TYPE_CHOICES, default="reunion")
    capacite    = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)
    actif       = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Salle de réunion"
        verbose_name_plural = "Salles de réunion"
        ordering = ["capacite", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.capacite} places)"


class Indisponibilite(models.Model):
    date_debut = models.DateField()
    date_fin   = models.DateField()
    motif      = models.TextField()
    temples    = models.ManyToManyField(Temple, blank=True, related_name="indisponibilites")
    salles     = models.ManyToManyField(SalleReunion, blank=True, related_name="indisponibilites")

    class Meta:
        verbose_name = "Indisponibilité"
        verbose_name_plural = "Indisponibilités"
        ordering = ["date_debut"]

    def __str__(self):
        return f"Indispo {self.date_debut} → {self.date_fin}"


class RegleRecurrence(models.Model):
    JOUR_CHOICES = [
        (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"),
        (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche"),
    ]
    SEMAINE_CHOICES = [
        (1, "1re semaine"), (2, "2e semaine"),
        (3, "3e semaine"), (4, "4e semaine"), (-1, "Dernière semaine"),
    ]

    loge           = models.ForeignKey(Loge, on_delete=models.CASCADE, related_name="regles")
    temple         = models.ForeignKey(Temple, on_delete=models.PROTECT)
    jour_semaine   = models.PositiveSmallIntegerField(choices=JOUR_CHOICES)
    numero_semaine = models.SmallIntegerField(choices=SEMAINE_CHOICES)
    heure_debut    = models.TimeField(default="19:30")
    heure_fin      = models.TimeField(default="22:30")
    mois_actifs    = models.JSONField(
        default=list,
        blank=True,
        help_text="Mois actifs (1=Jan … 12=Déc). Laisser vide = tous les mois (sauf juillet-août)."
    )
    actif          = models.BooleanField(default=True)
    date_debut     = models.DateField(
        null=True, blank=True,
        help_text="Début de validité (laisser vide = début de saison sept.)"
    )
    date_fin       = models.DateField(
        null=True, blank=True,
        help_text="Fin de validité (laisser vide = fin de saison juin)"
    )

    class Meta:
        verbose_name = "Règle de récurrence"
        verbose_name_plural = "Règles de récurrence"

    def __str__(self):
        return (
            f"{self.loge} – "
            f"{self.get_numero_semaine_display()} "
            f"{self.get_jour_semaine_display()}"
        )


class DemandeRegleRecurrence(models.Model):
    """Demande front-end d'une loge pour créer une règle de récurrence."""
    STATUT_CHOICES = [
        ("attente",  "En attente"),
        ("validee",  "Validée"),
        ("refusee",  "Refusée"),
    ]

    uuid            = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    loge            = models.ForeignKey(Loge, on_delete=models.CASCADE, related_name="demandes_regle")
    temple          = models.ForeignKey(Temple, on_delete=models.PROTECT)
    jour_semaine    = models.PositiveSmallIntegerField(choices=RegleRecurrence.JOUR_CHOICES)
    numero_semaine  = models.SmallIntegerField(choices=RegleRecurrence.SEMAINE_CHOICES)
    heure_debut     = models.TimeField()
    heure_fin       = models.TimeField()
    mois_actifs     = models.JSONField(default=list, blank=True)
    nom_demandeur   = models.CharField(max_length=100)
    email_demandeur = models.EmailField()
    commentaire     = models.TextField(blank=True)
    statut          = models.CharField(max_length=10, choices=STATUT_CHOICES, default="attente")
    date_demande    = models.DateTimeField(auto_now_add=True)
    regle_creee     = models.ForeignKey(
        RegleRecurrence, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="demande_source"
    )
    commentaire_admin = models.TextField(blank=True)

    class Meta:
        verbose_name = "Demande de règle de récurrence"
        verbose_name_plural = "Demandes de règles de récurrence"
        ordering = ["-date_demande"]

    def __str__(self):
        return (
            f"{self.loge} – {self.get_numero_semaine_display()} "
            f"{self.get_jour_semaine_display()} [{self.get_statut_display()}]"
        )


class Reservation(models.Model):
    TYPE_CHOICES = [
        ("reguliere",     "Régulière"),
        ("exceptionnelle","Exceptionnelle"),
    ]
    SOUS_TYPE_CHOICES = [
        ("standard", "Standard"),
        ("tbf",      "Tenue Blanche Fermée"),
        ("tbo",      "Tenue Blanche Ouverte"),
        ("funebre",  "Funèbre"),
    ]
    STATUT_CHOICES = [
        ("attente",  "En attente"),
        ("validee",  "Validée"),
        ("refusee",  "Refusée"),
    ]

    uuid             = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    loge             = models.ForeignKey(
        Loge, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations"
    )
    nom_organisation = models.CharField(
        max_length=200, blank=True,
        help_text="Si la loge n'est pas dans la liste, saisissez son nom ici."
    )
    temple           = models.ForeignKey(Temple, on_delete=models.PROTECT)
    cabinets         = models.ManyToManyField(SalleReunion, blank=True, related_name='reservations_cabinets')
    type_reservation = models.CharField(max_length=20, choices=TYPE_CHOICES, default="reguliere")
    sous_type        = models.CharField(max_length=10, choices=SOUS_TYPE_CHOICES, default="standard")
    profanes_admis   = models.BooleanField(default=False)
    statut           = models.CharField(max_length=20, choices=STATUT_CHOICES, default="attente")
    date             = models.DateField()
    heure_debut      = models.TimeField()
    heure_fin        = models.TimeField()
    besoin_agapes    = models.BooleanField(default=False)
    nombre_repas     = models.PositiveIntegerField(default=0)
    besoin_micro     = models.BooleanField(default=False)
    besoin_enceintes = models.BooleanField(default=False)
    nom_demandeur    = models.CharField(max_length=200)
    email_demandeur  = models.EmailField()
    commentaire      = models.TextField(blank=True)
    tarif            = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    regle_source     = models.ForeignKey(
        RegleRecurrence, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ["date", "heure_debut"]

    def nom_demandeur_ou_org(self):
        return self.loge.nom if self.loge else (self.nom_organisation or self.nom_demandeur)

    def __str__(self):
        org = self.loge or self.nom_organisation or self.nom_demandeur
        return f"{org} – {self.date} {self.heure_debut} ({self.temple})"


class ReservationSalle(models.Model):
    STATUT_CHOICES = [
        ("attente", "En attente"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
    ]

    HORAIRES_SUGGERES = [
        ("09:00", "09h00"),
        ("10:00", "10h00"),
        ("14:00", "14h00"),
        ("19:00", "19h00"),
        ("19:30", "19h30"),
        ("20:00", "20h00"),
    ]

    NOMBRE_CABINETS_CHOICES = [
        (1, "1 cabinet"),
        (2, "2 cabinets"),
        (3, "3 cabinets"),
    ]

    uuid            = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    salle           = models.ForeignKey(
        SalleReunion, on_delete=models.PROTECT, related_name="reservations"
    )
    date            = models.DateField()
    heure_debut     = models.TimeField()
    heure_fin       = models.TimeField()
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default="attente")
    nom_demandeur   = models.CharField(max_length=200)
    email_demandeur = models.EmailField()
    organisation    = models.CharField(max_length=200, blank=True, help_text="Loge, atelier ou autre")
    objet           = models.CharField(max_length=300, help_text="Objet de la réunion")
    nombre_participants = models.PositiveSmallIntegerField(default=1)
    nombre_cabinets  = models.PositiveSmallIntegerField(default=1, choices=NOMBRE_CABINETS_CHOICES)
    cabinet_prefere  = models.ForeignKey(
        SalleReunion, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reservations_preferees',
    )
    commentaire     = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réservation de salle"
        verbose_name_plural = "Réservations de salles"
        ordering = ["date", "heure_debut"]

    def __str__(self):
        return f"{self.salle} – {self.date} {self.heure_debut} ({self.nom_demandeur})"
