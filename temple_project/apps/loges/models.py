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

    RITE_CHOICES = [
        ("reaa",  "REAA — Rite Écossais Ancien et Accepté"),
        ("rer",   "RER — Rite Écossais Rectifié"),
        ("rf",    "RF — Rite Français"),
        ("rem",   "REM — Rite Écossais Moderne"),
        ("dh",    "DH — Droit Humain"),
        ("mem",   "MEM — Memphis-Misraïm"),
        ("autre", "Autre"),
    ]

    nom                   = models.CharField(max_length=200)
    abreviation           = models.CharField(max_length=20, blank=True)
    obedience             = models.ForeignKey(Obedience, on_delete=models.PROTECT, related_name="loges")
    type_loge             = models.CharField(max_length=20, choices=TYPE_CHOICES, default="loge")
    rite                  = models.CharField(max_length=10, choices=RITE_CHOICES, blank=True, default="")
    email                 = models.EmailField(blank=True)
    effectif_total        = models.PositiveIntegerField(default=0)
    effectif_moyen_agapes = models.PositiveIntegerField(default=0)
    actif                 = models.BooleanField(default=True)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Loge"
        verbose_name_plural = "Loges"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.abreviation})" if self.abreviation else self.nom
