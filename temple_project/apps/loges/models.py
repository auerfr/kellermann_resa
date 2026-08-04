from django.db import models


class Obedience(models.Model):
    nom = models.CharField(max_length=200, unique=True)

    class Meta:
        verbose_name = "Obédience"
        verbose_name_plural = "Obédiences"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Loge(models.Model):
    TYPE_CHOICES = [
        ("loge",       "Loge"),
        ("haut_grade", "Haut Grade"),
    ]

    STATUT_CHOICES = [
        ("active",        "Active"),
        ("a_reconfirmer", "À reconfirmer"),
        ("inactive",      "Inactive"),
    ]

    RITE_CHOICES = [
        ("reaa",      "REAA — Rite Écossais Ancien et Accepté"),
        ("rer",       "RER — Rite Écossais Rectifié"),
        ("rf",        "RF — Rite Français"),
        ("rf_reaa",   "RF/REAA — Rite Français et Rite Écossais Ancien et Accepté"),
        ("rem",       "REM — Rite Écossais Moderne"),
        ("dh",        "DH — Droit Humain"),
        ("mem",       "MEM — Memphis-Misraïm"),
        ("rapmm",     "RAPMM — Rite Ancien et Primitif de Memphis-Misraïm"),
        ("rmfr",      "RMFR — Rite Moderne Français Rectifié"),
        ("emulation", "Emulation"),
        ("marque",    "Marque et York"),
        ("autre",     "Autre"),
    ]

    nom                   = models.CharField(max_length=200)
    abreviation           = models.CharField(max_length=20, blank=True)
    association           = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Nom d'association / atelier complémentaire (ex. « P46 - La Sagesse »)",
    )
    obedience             = models.ForeignKey(Obedience, on_delete=models.PROTECT, related_name="loges")
    type_loge             = models.CharField(max_length=20, choices=TYPE_CHOICES, default="loge")
    rite                  = models.CharField(max_length=20, choices=RITE_CHOICES, blank=True, default="")
    rite_precision        = models.CharField(max_length=200, blank=True, default="")
    nom_contact           = models.CharField(max_length=200, blank=True, default="", help_text="Nom du contact / vénérable")
    email                 = models.EmailField(blank=True)
    telephone             = models.CharField(max_length=30, blank=True, default="")
    effectif_total        = models.PositiveIntegerField(default=0)
    effectif_moyen_agapes = models.PositiveIntegerField(default=0)
    couverts_habituels    = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre de couverts habituels renseigné par le traiteur (prioritaire sur effectif_moyen_agapes)"
    )
    actif                 = models.BooleanField(default=True)
    statut                = models.CharField(
        max_length=15, choices=STATUT_CHOICES, default="active",
        help_text="Active = confirmée ; À reconfirmer = pas de retour pour la nouvelle saison ; Inactive = dissoute/partie",
    )
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Loge"
        verbose_name_plural = "Loges"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.abreviation})" if self.abreviation else self.nom
