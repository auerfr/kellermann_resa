from django.contrib import admin
from .models import (
    Temple, Cabinet, SalleReunion,
    Indisponibilite, RegleRecurrence,
    Reservation, ReservationSalle,
)


@admin.register(Temple)
class TempleAdmin(admin.ModelAdmin):
    list_display = ["nom", "capacite"]


@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin):
    list_display = ["numero", "nom"]


@admin.register(SalleReunion)
class SalleReunionAdmin(admin.ModelAdmin):
    list_display  = ["nom", "capacite", "actif"]
    list_filter   = ["actif"]
    list_editable = ["capacite", "actif"]


@admin.register(Indisponibilite)
class IndisponibiliteAdmin(admin.ModelAdmin):
    list_display = ["date_debut", "date_fin", "motif"]
    filter_horizontal = ["temples", "salles"]


@admin.register(RegleRecurrence)
class RegleAdmin(admin.ModelAdmin):
    list_display  = ["loge", "numero_semaine", "jour_semaine", "temple",
                     "heure_debut", "heure_fin", "date_debut", "date_fin", "actif"]
    list_filter   = ["actif", "temple", "jour_semaine"]
    search_fields = ["loge__nom"]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display  = ["loge", "date", "heure_debut", "temple",
                     "type_reservation", "statut"]
    list_filter   = ["statut", "type_reservation", "temple"]
    search_fields = ["loge__nom", "email_demandeur"]
    date_hierarchy = "date"


@admin.register(ReservationSalle)
class ReservationSalleAdmin(admin.ModelAdmin):
    list_display  = ["salle", "date", "heure_debut", "heure_fin",
                     "nom_demandeur", "organisation", "nombre_participants", "statut"]
    list_filter   = ["statut", "salle"]
    search_fields = ["nom_demandeur", "email_demandeur", "organisation", "objet"]
    date_hierarchy = "date"
