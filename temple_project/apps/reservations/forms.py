from django import forms
from .models import Reservation, ReservationSalle, SalleReunion

HORAIRES = [
    ("09:00", "09h00"), ("09:30", "09h30"),
    ("10:00", "10h00"), ("10:30", "10h30"),
    ("14:00", "14h00"), ("14:30", "14h30"),
    ("15:00", "15h00"), ("18:00", "18h00"),
    ("19:00", "19h00"), ("19:30", "19h30"),
    ("20:00", "20h00"), ("20:30", "20h30"),
    ("21:00", "21h00"), ("22:00", "22h00"),
    ("22:30", "22h30"), ("23:00", "23h00"),
]


class DemandeReservationForm(forms.ModelForm):
    heure_debut = forms.ChoiceField(
        choices=HORAIRES, label="Heure de début",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    heure_fin = forms.ChoiceField(
        choices=HORAIRES, label="Heure de fin",
        initial="22:30",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    cabinets = forms.ModelMultipleChoiceField(
        queryset=SalleReunion.objects.filter(type_salle='cabinet_reflexion', actif=True),
        widget=forms.CheckboxSelectMultiple(),
        required=False
    )

    class Meta:
        model = Reservation
        fields = [
            "loge", "nom_organisation", "temple", "date",
            "heure_debut", "heure_fin",
            "sous_type",
            "besoin_agapes", "nombre_repas",
            "besoin_micro", "besoin_enceintes",
            "profanes_admis",
            "nom_demandeur", "email_demandeur", "commentaire",
        ]
        widgets = {
            "date":             forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "loge":             forms.Select(attrs={"class": "form-select"}),
            "nom_organisation": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex : Association Fraternelle du Monde, Atelier…"
            }),
            "temple":           forms.Select(attrs={"class": "form-select"}),
            "sous_type":        forms.Select(attrs={"class": "form-select"}),
            "cabinets":         forms.CheckboxSelectMultiple(),
            "profanes_admis":   forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "nom_demandeur":    forms.TextInput(attrs={"class": "form-control"}),
            "email_demandeur":  forms.EmailInput(attrs={"class": "form-control"}),
            "commentaire":      forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "nombre_repas":     forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('loge') and not cleaned.get('nom_organisation', '').strip():
            raise forms.ValidationError(
                "Sélectionnez une loge dans la liste ou saisissez le nom de votre organisation."
            )
        return cleaned


class DemandeReservationSalleForm(forms.ModelForm):
    heure_debut = forms.ChoiceField(
        choices=HORAIRES, label="Heure de début",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    heure_fin = forms.ChoiceField(
        choices=HORAIRES, label="Heure de fin",
        initial="22:30",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = ReservationSalle
        fields = [
            "salle", "date",
            "heure_debut", "heure_fin",
            "nom_demandeur", "email_demandeur",
            "organisation", "objet",
            "nombre_participants", "commentaire",
        ]
        widgets = {
            "salle":               forms.Select(attrs={"class": "form-select"}),
            "date":                forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "nom_demandeur":       forms.TextInput(attrs={"class": "form-control"}),
            "email_demandeur":     forms.EmailInput(attrs={"class": "form-control"}),
            "organisation":        forms.TextInput(attrs={"class": "form-control",
                                    "placeholder": "Loge, atelier ou organisme"}),
            "objet":               forms.TextInput(attrs={"class": "form-control",
                                    "placeholder": "Ex : Réunion de bureau, Conseil d'administration..."}),
            "nombre_participants": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "commentaire":         forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }


class DemandeCabinetsForm(forms.Form):
    loge = forms.ModelChoiceField(
        queryset=None,  # Sera défini dans __init__
        label="Loge",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    heure_debut = forms.ChoiceField(
        choices=HORAIRES, label="Heure de début",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    heure_fin = forms.ChoiceField(
        choices=HORAIRES, label="Heure de fin",
        initial="22:30",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    nombre_cabinets = forms.ChoiceField(
        choices=[(1, "1 cabinet"), (2, "2 cabinets"), (3, "3 cabinets")],
        label="Nombre de cabinets",
        initial=1,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    nom_demandeur = forms.CharField(
        max_length=200, label="Nom du demandeur",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email_demandeur = forms.EmailField(
        label="Email du demandeur",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    organisation = forms.CharField(
        max_length=200, required=False, label="Organisation",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Loge, atelier ou organisme"
        })
    )
    objet = forms.CharField(
        max_length=300, label="Objet",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex : Réflexion personnelle, préparation rituelle..."
        })
    )
    commentaire = forms.CharField(
        required=False, label="Commentaire",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        from temple_project.apps.loges.models import Loge
        super().__init__(*args, **kwargs)
        self.fields['loge'].queryset = Loge.objects.all().order_by('nom')


class DemandeBanquetForm(forms.Form):
    loge = forms.ModelChoiceField(
        queryset=None,  # Sera défini dans __init__
        label="Loge",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    heure_debut = forms.ChoiceField(
        choices=HORAIRES, label="Heure de début",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    heure_fin = forms.ChoiceField(
        choices=HORAIRES, label="Heure de fin",
        initial="22:30",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    nombre_repas = forms.IntegerField(
        label="Nombre de repas",
        min_value=1,
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
    commentaire = forms.CharField(
        required=False, label="Commentaire",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        from temple_project.apps.loges.models import Loge
        super().__init__(*args, **kwargs)
        self.fields['loge'].queryset = Loge.objects.all().order_by('nom')
