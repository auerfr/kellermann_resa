from django import forms
from temple_project.apps.reservations.models import (
    SalleReunion, Reservation, ReservationSalle, BlocageCreneaux
)
from temple_project.apps.loges.models import Loge


class ReservationDirecteForm(forms.Form):
    """Formulaire de réservation directe pour l'admin (temple ou salle, statut validée)."""
    TYPE_CHOICES = [
        ("temple", "Temple"),
        ("salle",  "Salle / Agapes"),
    ]

    type_resa   = forms.ChoiceField(choices=TYPE_CHOICES, label="Type de réservation",
                                    widget=forms.Select(attrs={"class": "form-select"}))
    loge        = forms.ModelChoiceField(
        queryset=Loge.objects.filter(actif=True).order_by("nom"),
        required=False, label="Loge (si connue)",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Aucune loge —",
    )
    organisation = forms.CharField(
        max_length=200, required=False, label="Organisation / nom libre",
        widget=forms.TextInput(attrs={"class": "form-control",
                                      "placeholder": "Si la loge n'est pas dans la liste"})
    )
    from temple_project.apps.reservations.models import Temple as _Temple
    temple      = forms.ModelChoiceField(
        queryset=_Temple.objects.all(),
        required=False, label="Temple",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Choisir un temple —",
    )
    salle       = forms.ModelChoiceField(
        queryset=SalleReunion.objects.filter(actif=True, type_salle="agapes").order_by("nom"),
        required=False, label="Salle agapes",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Choisir une salle —",
    )
    date        = forms.DateField(label="Date",
                                  widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    heure_debut = forms.TimeField(label="Heure de début",
                                  widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}))
    heure_fin   = forms.TimeField(label="Heure de fin",
                                  widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}))
    nombre_repas = forms.IntegerField(
        min_value=0, required=False, initial=0, label="Nombre de couverts",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    nom_demandeur = forms.CharField(
        max_length=200, label="Nom du demandeur",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email_demandeur = forms.EmailField(
        label="Email du demandeur",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    note = forms.CharField(
        required=False, label="Note / commentaire",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    def clean(self):
        cleaned = super().clean()
        type_resa = cleaned.get("type_resa")
        if type_resa == "temple" and not cleaned.get("temple"):
            self.add_error("temple", "Veuillez choisir un temple.")
        if type_resa == "salle" and not cleaned.get("salle"):
            self.add_error("salle", "Veuillez choisir une salle agapes.")
        hd = cleaned.get("heure_debut")
        hf = cleaned.get("heure_fin")
        if hd and hf and hf <= hd:
            self.add_error("heure_fin", "L'heure de fin doit être après l'heure de début.")
        return cleaned


class TraiteurReservationDirecteForm(forms.Form):
    """Formulaire de réservation directe simplifié pour le traiteur (salle agapes uniquement)."""

    loge = forms.ModelChoiceField(
        queryset=Loge.objects.filter(actif=True).order_by("nom"),
        required=False, label="Loge",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Aucune loge —",
    )
    organisation = forms.CharField(
        max_length=200, required=False, label="Organisation / nom libre",
        widget=forms.TextInput(attrs={"class": "form-control",
                                      "placeholder": "Si la loge n'est pas dans la liste"})
    )
    salle = forms.ModelChoiceField(
        queryset=SalleReunion.objects.filter(actif=True, type_salle="agapes").order_by("nom"),
        required=True, label="Salle d'agapes",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Choisir une salle —",
    )
    date        = forms.DateField(label="Date",
                                  widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    heure_debut = forms.TimeField(label="Heure de début",
                                  widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}))
    heure_fin   = forms.TimeField(label="Heure de fin",
                                  widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}))
    nombre_repas = forms.IntegerField(
        min_value=0, required=False, initial=0, label="Nombre de couverts",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    commentaire = forms.CharField(
        required=False, label="Commentaire",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                     "placeholder": "Informations complémentaires…"})
    )

    def clean(self):
        cleaned = super().clean()
        hd = cleaned.get("heure_debut")
        hf = cleaned.get("heure_fin")
        if hd and hf and hf <= hd:
            self.add_error("heure_fin", "L'heure de fin doit être après l'heure de début.")
        if not cleaned.get("loge") and not cleaned.get("organisation"):
            self.add_error("organisation", "Indiquez une loge ou un nom d'organisation.")
        return cleaned


class BlocageCreneauxForm(forms.ModelForm):
    """Formulaire de blocage de créneau (salles agapes uniquement)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restreindre aux salles agapes actives
        self.fields["salles"].queryset = SalleReunion.objects.filter(
            actif=True, type_salle="agapes"
        ).order_by("nom")

    class Meta:
        model  = BlocageCreneaux
        fields = ["date", "heure_debut", "heure_fin", "salles", "motif"]
        widgets = {
            "date":        forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin":   forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "salles":      forms.CheckboxSelectMultiple(),
            "motif":       forms.TextInput(attrs={"class": "form-control",
                                                  "placeholder": "Ex : Fermeture exceptionnelle, Entretien…"}),
        }
        labels = {
            "date":        "Date",
            "heure_debut": "Heure de début",
            "heure_fin":   "Heure de fin",
            "salles":      "Salle(s) d'agapes concernée(s)",
            "motif":       "Motif",
        }

    def clean(self):
        cleaned = super().clean()
        hd = cleaned.get("heure_debut")
        hf = cleaned.get("heure_fin")
        if hd and hf and hf <= hd:
            self.add_error("heure_fin", "L'heure de fin doit être après l'heure de début.")
        if not cleaned.get("salles"):
            raise forms.ValidationError("Sélectionnez au moins une salle d'agapes à bloquer.")
        return cleaned


class NotificationCouvertsForm(forms.Form):
    """Formulaire permettant à un membre de notifier le traiteur d'un changement de couverts."""

    loge = forms.ModelChoiceField(
        queryset=Loge.objects.filter(actif=True).order_by("nom"),
        required=True, label="Loge",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="— Sélectionner votre loge —",
    )
    date_tenue = forms.DateField(
        label="Date de la tenue",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    nombre_couverts = forms.IntegerField(
        min_value=1, label="Nombre de couverts prévu",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ex : 42"})
    )
    commentaire = forms.CharField(
        required=False, label="Commentaire",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                     "placeholder": "Ex : 5 visiteurs supplémentaires ce soir…"})
    )
    email_contact = forms.EmailField(
        label="Votre email",
        widget=forms.EmailInput(attrs={"class": "form-control",
                                       "placeholder": "Pour confirmation de réception"})
    )
