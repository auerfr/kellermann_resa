from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.conf import settings
from django.core.mail import send_mail
from .models import (
    Temple, Cabinet, SalleReunion,
    Indisponibilite, RegleRecurrence,
    Reservation, ReservationSalle,
    DemandeRegleRecurrence,
)


MOIS_CHOICES = [
    (1, "Jan"), (2, "Fév"), (3, "Mar"), (4, "Avr"),
    (5, "Mai"), (6, "Juin"), (7, "Juil"), (8, "Aoû"),
    (9, "Sep"), (10, "Oct"), (11, "Nov"), (12, "Déc"),
]


TRANCHES_HORAIRES = [
    ("Matin",           "09:00", "12:00"),
    ("Après-midi",      "14:00", "17:00"),
    ("Soir",            "19:00", "22:30"),
    ("Journée complète","09:00", "17:00"),
]


class TrancheHoraireWidget(forms.Widget):
    """Boutons raccourcis pour remplir heure_debut / heure_fin."""

    def render(self, name, value, attrs=None, renderer=None):
        html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;">'
        for label, debut, fin in TRANCHES_HORAIRES:
            html += (
                f'<button type="button" onclick="setHoraire(\'{debut}\',\'{fin}\')" '
                f'style="padding:3px 10px;border:1px solid #ccc;border-radius:4px;'
                f'background:#f8f8f8;cursor:pointer;font-size:12px;">'
                f'{label} <small style="color:#888;">({debut}–{fin})</small></button>'
            )
        html += '</div>'
        html += (
            '<script>'
            'function setHoraire(d,f){'
            'var fd=document.getElementById("id_heure_debut");'
            'var ff=document.getElementById("id_heure_fin");'
            'if(fd)fd.value=d; if(ff)ff.value=f;}'
            '</script>'
        )
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        return None


class TrancheHoraireField(forms.Field):
    widget = TrancheHoraireWidget
    required = False

    def to_python(self, value):
        return None


class MoisActifsWidget(forms.Widget):
    """Widget cases à cocher horizontales pour les mois actifs."""

    def render(self, name, value, attrs=None, renderer=None):
        if not isinstance(value, list):
            value = []
        html = '<div style="display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:4px;">'
        for num, label in MOIS_CHOICES:
            checked = "checked" if num in value else ""
            html += (
                f'<label style="display:flex;align-items:center;gap:4px;font-weight:normal;cursor:pointer;">'
                f'<input type="checkbox" name="{name}" value="{num}" {checked}>'
                f'{label}</label>'
            )
        html += '</div>'
        html += '<p class="help" style="color:#999;font-size:11px;margin-top:4px;">Laisser tout décoché = tous les mois (juil.–août exclus automatiquement).</p>'
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        return [int(v) for v in data.getlist(name) if v.isdigit()]


class MoisActifsField(forms.Field):
    widget = MoisActifsWidget

    def to_python(self, value):
        if not value:
            return []
        return value

    def prepare_value(self, value):
        return value or []


class RegleRecurrenceForm(forms.ModelForm):
    tranche_horaire = TrancheHoraireField(label="Raccourci horaire", required=False)
    mois_actifs     = MoisActifsField(required=False, label="Mois actifs")

    class Meta:
        model  = RegleRecurrence
        fields = "__all__"

    def save(self, commit=True):
        # tranche_horaire est un champ virtuel, ne pas le passer au modèle
        self.cleaned_data.pop("tranche_horaire", None)
        return super().save(commit=commit)


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
    form          = RegleRecurrenceForm
    list_display  = ["loge", "numero_semaine", "jour_semaine", "temple",
                     "heure_debut", "heure_fin", "mois_actifs_display", "actif"]
    list_filter   = ["actif", "temple", "jour_semaine"]
    search_fields = ["loge__nom"]
    fieldsets = (
        (None, {
            "fields": ("loge", "temple", "jour_semaine", "numero_semaine"),
        }),
        ("Horaires", {
            "fields": ("tranche_horaire", "heure_debut", "heure_fin"),
        }),
        ("Mois actifs", {
            "fields": ("mois_actifs",),
            "description": "Cochez les mois où cette loge se réunit. Tout décoché = tous les mois.",
        }),
        ("Validité & statut", {
            "fields": ("date_debut", "date_fin", "actif"),
        }),
    )

    @admin.display(description="Mois actifs")
    def mois_actifs_display(self, obj):
        if not obj.mois_actifs:
            return "Tous"
        noms = {num: label for num, label in MOIS_CHOICES}
        return ", ".join(noms[m] for m in sorted(obj.mois_actifs) if m in noms)


@admin.register(DemandeRegleRecurrence)
class DemandeRegleAdmin(admin.ModelAdmin):
    list_display  = ["loge", "temple", "frequence_display", "horaires_display",
                     "mois_display", "nom_demandeur", "date_demande", "statut_badge"]
    list_filter   = ["statut", "temple", "jour_semaine"]
    search_fields = ["loge__nom", "nom_demandeur", "email_demandeur"]
    readonly_fields = ["uuid", "loge", "temple", "jour_semaine", "numero_semaine",
                       "heure_debut", "heure_fin", "mois_actifs", "nom_demandeur",
                       "email_demandeur", "commentaire", "date_demande", "regle_creee"]
    fieldsets = (
        ("Demande (lecture seule)", {
            "fields": ("uuid", "loge", "temple", "jour_semaine", "numero_semaine",
                       "heure_debut", "heure_fin", "mois_actifs",
                       "nom_demandeur", "email_demandeur", "commentaire", "date_demande"),
        }),
        ("Décision", {
            "fields": ("statut", "commentaire_admin", "regle_creee"),
        }),
    )
    actions = ["valider_demandes", "refuser_demandes"]

    def save_model(self, request, obj, form, change):
        ancienne_statut = DemandeRegleRecurrence.objects.filter(pk=obj.pk).values_list("statut", flat=True).first()
        super().save_model(request, obj, form, change)
        if obj.statut == "validee" and ancienne_statut != "validee":
            # Créer la règle de récurrence
            regle = RegleRecurrence.objects.create(
                loge=obj.loge, temple=obj.temple,
                jour_semaine=obj.jour_semaine, numero_semaine=obj.numero_semaine,
                heure_debut=obj.heure_debut, heure_fin=obj.heure_fin,
                mois_actifs=obj.mois_actifs, actif=True,
            )
            obj.regle_creee = regle
            obj.save(update_fields=["regle_creee"])
            self._notifier(obj, validee=True)
            messages.success(request, f"Règle créée ({regle}) et loge notifiée.")
        elif obj.statut == "refusee" and ancienne_statut != "refusee":
            self._notifier(obj, validee=False)
            messages.info(request, "Demande refusée, loge notifiée.")

    def _notifier(self, obj, validee):
        if validee:
            sujet = f"[Kellermann] Votre demande de récurrence a été validée"
            corps = (
                f"Bonjour {obj.nom_demandeur},\n\n"
                f"Votre demande de règle de récurrence a été acceptée.\n\n"
                f"  Loge      : {obj.loge}\n"
                f"  Temple    : {obj.temple}\n"
                f"  Fréquence : {obj.get_numero_semaine_display()} {obj.get_jour_semaine_display()}\n"
                f"  Horaires  : {obj.heure_debut:%H:%M} – {obj.heure_fin:%H:%M}\n\n"
            )
        else:
            sujet = f"[Kellermann] Votre demande de récurrence n'a pas été retenue"
            corps = (
                f"Bonjour {obj.nom_demandeur},\n\n"
                f"Votre demande de règle de récurrence n'a pas pu être acceptée.\n\n"
            )
        if obj.commentaire_admin:
            corps += f"Message de l'administration :\n{obj.commentaire_admin}\n\n"
        corps += "Fraternellement,\nL'administration des Temples Kellermann"
        send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL,
                  [obj.email_demandeur], fail_silently=True)

    @admin.action(description="Valider les demandes sélectionnées")
    def valider_demandes(self, request, queryset):
        for obj in queryset.filter(statut="attente"):
            obj.statut = "validee"
            self.save_model(request, obj, None, True)

    @admin.action(description="Refuser les demandes sélectionnées")
    def refuser_demandes(self, request, queryset):
        for obj in queryset.filter(statut="attente"):
            obj.statut = "refusee"
            self.save_model(request, obj, None, True)

    @admin.display(description="Fréquence")
    def frequence_display(self, obj):
        return f"{obj.get_numero_semaine_display()} {obj.get_jour_semaine_display()}"

    @admin.display(description="Horaires")
    def horaires_display(self, obj):
        return f"{obj.heure_debut:%H:%M}–{obj.heure_fin:%H:%M}"

    @admin.display(description="Mois")
    def mois_display(self, obj):
        if not obj.mois_actifs:
            return "Tous"
        noms = {num: label for num, label in MOIS_CHOICES}
        return ", ".join(noms[m] for m in sorted(obj.mois_actifs) if m in noms)

    @admin.display(description="Statut")
    def statut_badge(self, obj):
        colors = {"attente": "#F59E0B", "validee": "#16A34A", "refusee": "#DC2626"}
        c = colors.get(obj.statut, "#6B7280")
        return mark_safe(
            f'<span style="background:{c};color:white;padding:2px 8px;'
            f'border-radius:4px;font-size:11px;">{obj.get_statut_display()}</span>'
        )


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
