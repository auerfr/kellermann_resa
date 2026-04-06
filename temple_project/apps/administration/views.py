from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin
from django.http import HttpResponse
from datetime import date, timedelta
import calendar
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from temple_project.apps.reservations.models import (
    Reservation, RegleRecurrence, Temple, SalleReunion, ReservationSalle
)
from temple_project.apps.loges.models import Loge, Obedience
from .models import Parametres


# ── Tableau de bord ───────────────────────────────────────────────────────────

@login_required
def tableau_de_bord(request):
    reservations_attente  = Reservation.objects.filter(statut='attente').select_related('loge', 'temple').order_by('date')
    reservations_recentes = Reservation.objects.order_by('-created_at')[:10]
    reservations_salle_attente = ReservationSalle.objects.filter(
        statut='attente'
    ).select_related('salle').order_by('date')
    context = {
        'attente':         reservations_attente,
        'recentes':        reservations_recentes,
        'nb_attente':      reservations_attente.count(),
        'nb_loges':        Loge.objects.count(),
        'nb_reservations': Reservation.objects.count(),
        'nb_regles':       RegleRecurrence.objects.filter(actif=True).count(),
        'attente_salles': reservations_salle_attente,
        'nb_attente_salles': reservations_salle_attente.count(),
    }
    return render(request, 'administration/tableau_de_bord.html', context)


# ── Validation réservations ───────────────────────────────────────────────────

@login_required
def valider_reservation(request, pk):
    resa = get_object_or_404(Reservation, pk=pk)

    # Détection conflits
    conflits = Reservation.objects.filter(
        temple=resa.temple,
        date=resa.date,
        statut='validee',
        heure_debut__lt=resa.heure_fin,
        heure_fin__gt=resa.heure_debut,
    ).exclude(pk=pk).select_related('loge')

    if request.method == 'POST':
        action            = request.POST.get('action')
        commentaire_admin = request.POST.get('commentaire_admin', '').strip()

        if action not in ('valider', 'refuser'):
            messages.error(request, "Action invalide.")
            return redirect('administration:tableau_de_bord')

        resa.statut = 'validee' if action == 'valider' else 'refusee'
        resa.save()

        _envoyer_email_decision(resa, action, commentaire_admin)

        if action == 'valider':
            messages.success(request, f"Demande de {resa.loge} validée — email envoyé à {resa.email_demandeur}.")
        else:
            messages.warning(request, f"Demande de {resa.loge} refusée — email envoyé à {resa.email_demandeur}.")

        return redirect('administration:tableau_de_bord')

    return render(request, 'administration/valider_reservation.html', {
        'reservation': resa,
        'conflits':    conflits,
    })


@login_required
def valider_reservation_salle(request, pk):
    resa = get_object_or_404(ReservationSalle, pk=pk)
    is_cabinet = resa.salle.type_salle == 'cabinet_reflexion'

    # Détection conflits (non applicable aux cabinets — chacun a sa propre salle)
    conflits = ReservationSalle.objects.filter(
        salle=resa.salle,
        date=resa.date,
        statut='validee',
        heure_debut__lt=resa.heure_fin,
        heure_fin__gt=resa.heure_debut,
    ).exclude(pk=pk)

    # Disponibilité des cabinets (en excluant la demande en cours)
    cabinets_dispo = []
    if is_cabinet:
        from temple_project.apps.reservations.models import SalleReunion
        for cabinet in SalleReunion.objects.filter(type_salle='cabinet_reflexion', actif=True).order_by('nom'):
            occupe = ReservationSalle.objects.filter(
                salle=cabinet,
                date=resa.date,
                heure_debut__lt=resa.heure_fin,
                heure_fin__gt=resa.heure_debut,
                statut__in=['attente', 'validee'],
            ).exclude(pk=pk).exists()
            cabinets_dispo.append({
                'cabinet': cabinet,
                'libre': not occupe,
                'prefere': resa.cabinet_prefere_id == cabinet.pk,
            })

    if request.method == 'POST':
        action            = request.POST.get('action')
        commentaire_admin = request.POST.get('commentaire_admin', '').strip()

        if action not in ('valider', 'refuser'):
            messages.error(request, "Action invalide.")
            return redirect('administration:tableau_de_bord')

        if action == 'valider' and is_cabinet:
            cabinet_attribue_id = request.POST.get('cabinet_attribue_id')
            if cabinet_attribue_id:
                from temple_project.apps.reservations.models import SalleReunion
                try:
                    resa.salle = SalleReunion.objects.get(pk=cabinet_attribue_id, type_salle='cabinet_reflexion')
                except SalleReunion.DoesNotExist:
                    pass

        resa.statut = 'validee' if action == 'valider' else 'refusee'
        resa.save()

        _envoyer_email_decision_salle(resa, action, commentaire_admin)

        if action == 'valider':
            messages.success(request, f"Demande de salle pour {resa.organisation} validée — email envoyé à {resa.email_demandeur}.")
        else:
            messages.warning(request, f"Demande de salle pour {resa.organisation} refusée — email envoyé à {resa.email_demandeur}.")

        return redirect('administration:tableau_de_bord')

    return render(request, 'administration/valider_reservation_salle.html', {
        'reservation':   resa,
        'conflits':      conflits,
        'is_cabinet':    is_cabinet,
        'cabinets_dispo': cabinets_dispo,
    })


def _envoyer_email_decision(resa, action, commentaire_admin=''):
    validee = (action == 'valider')
    sujet = (
        f"[Kellermann] Votre demande du {resa.date:%d/%m/%Y} a ete validee"
        if validee else
        f"[Kellermann] Votre demande du {resa.date:%d/%m/%Y} n'a pas pu etre accordee"
    )
    corps = f"""Bonjour {resa.nom_demandeur},

{"Votre demande de reservation a ete validee." if validee else "Votre demande de reservation n'a pas pu etre acceptee."}

Details :
  Temple    : {resa.temple}
  Date      : {resa.date:%d/%m/%Y}
  Horaires  : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
  Type      : {resa.get_type_reservation_display()}
"""
    if resa.besoin_agapes:
        corps += f"  Agapes    : {resa.nombre_repas} couverts\n"
    if commentaire_admin:
        corps += f"\nMessage de l'administrateur :\n{commentaire_admin}\n"
    corps += "\nFraternellement,\nL'administration des Temples Kellermann\n"

    try:
        send_mail_kellermann(sujet, corps, [resa.email_demandeur], fail_silently=False)
    except Exception as e:
        print(f"Erreur email decision : {e}")


def _envoyer_email_decision_salle(resa, action, commentaire_admin=''):
    validee = (action == 'valider')
    is_cabinet = resa.salle.type_salle == 'cabinet_reflexion'

    if is_cabinet:
        sujet = (
            f"[Kellermann] Votre demande de cabinet du {resa.date:%d/%m/%Y} a ete validee"
            if validee else
            f"[Kellermann] Votre demande de cabinet du {resa.date:%d/%m/%Y} n'a pas pu etre accordee"
        )
        if validee:
            corps = f"""Bonjour {resa.nom_demandeur},

Votre demande de cabinet de reflexion a ete validee.

Cabinet attribue : {resa.salle.nom}
Date             : {resa.date:%d/%m/%Y}
Horaires         : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
Objet            : {resa.objet}
"""
        else:
            corps = f"""Bonjour {resa.nom_demandeur},

Votre demande de cabinet de reflexion du {resa.date:%d/%m/%Y} n'a pas pu etre accordee.

Date     : {resa.date:%d/%m/%Y}
Horaires : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
Objet    : {resa.objet}
"""
    else:
        sujet = (
            f"[Kellermann] Votre demande de salle du {resa.date:%d/%m/%Y} a ete validee"
            if validee else
            f"[Kellermann] Votre demande de salle du {resa.date:%d/%m/%Y} n'a pas pu etre accordee"
        )
        corps = f"""Bonjour {resa.nom_demandeur},

{"Votre demande de reservation de salle a ete validee." if validee else "Votre demande de reservation de salle n'a pas pu etre acceptee."}

Details :
  Salle     : {resa.salle}
  Date      : {resa.date:%d/%m/%Y}
  Horaires  : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
  Objet     : {resa.objet}
"""

    if commentaire_admin:
        corps += f"\nMessage de l'administrateur :\n{commentaire_admin}\n"
    corps += "\nFraternellement,\nL'administration des Temples Kellermann\n"

    try:
        send_mail_kellermann(sujet, corps, [resa.email_demandeur], fail_silently=False)
    except Exception as e:
        print(f"Erreur email decision salle : {e}")


# ── Règles de récurrence ──────────────────────────────────────────────────────

@login_required
def regles_liste(request):
    regles = RegleRecurrence.objects.select_related('loge', 'loge__obedience', 'temple').order_by('temple__nom', 'jour_semaine', 'numero_semaine')
    if request.GET.get('temple'):
        regles = regles.filter(temple_id=request.GET['temple'])
    if request.GET.get('loge'):
        regles = regles.filter(loge_id=request.GET['loge'])
    return render(request, 'administration/regles_liste.html', {
        'regles': regles, 'temples': Temple.objects.all(),
        'loges': Loge.objects.filter(actif=True).order_by('nom'),
        'nb_regles': regles.count(),
    })


@login_required
def regle_form(request, pk=None):
    regle = get_object_or_404(RegleRecurrence, pk=pk) if pk else None
    if request.method == 'POST':
        try:
            mois_actifs = [int(m) for m in request.POST.getlist('mois_actifs') if m.isdigit()]
            data = {
                'loge_id': request.POST['loge'], 'temple_id': request.POST['temple'],
                'jour_semaine': int(request.POST['jour_semaine']),
                'numero_semaine': int(request.POST['numero_semaine']),
                'heure_debut': request.POST['heure_debut'], 'heure_fin': request.POST['heure_fin'],
                'mois_actifs': mois_actifs,
                'actif': request.POST.get('actif') == 'on',
                'date_debut': request.POST.get('date_debut') or None,
                'date_fin': request.POST.get('date_fin') or None,
            }
            if regle:
                for k, v in data.items():
                    setattr(regle, k, v)
                regle.save()
                messages.success(request, "Règle modifiée.")
            else:
                RegleRecurrence.objects.create(**data)
                messages.success(request, "Règle ajoutée.")
            return redirect('administration:regles_liste')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'administration/regle_form.html', {
        'regle': regle, 'temples': Temple.objects.all(),
        'loges': Loge.objects.filter(actif=True).order_by('nom'),
        'jours': RegleRecurrence.JOUR_CHOICES,
        'semaines': RegleRecurrence.SEMAINE_CHOICES,
        'horaires': [
            ('09:00','09h00'),('09:30','09h30'),('10:00','10h00'),('10:30','10h30'),
            ('11:00','11h00'),('11:30','11h30'),('12:00','12h00'),
            ('14:00','14h00'),('14:30','14h30'),('15:00','15h00'),('15:30','15h30'),
            ('16:00','16h00'),('16:30','16h30'),('17:00','17h00'),
            ('19:00','19h00'),('19:30','19h30'),('20:00','20h00'),('20:30','20h30'),
            ('21:00','21h00'),('22:00','22h00'),('22:30','22h30'),('23:00','23h00'),
        ],
        'tranches': [
            ('matin',    'Matin',       '09:00', '12:00'),
            ('apmidi',   'Après-midi',  '14:00', '17:00'),
            ('soir',     'Soir',        '19:00', '22:30'),
            ('journee',  'Journée',     '09:00', '17:00'),
        ],
        'mois_choices': [
            (1,'Janvier'),(2,'Février'),(3,'Mars'),(4,'Avril'),
            (5,'Mai'),(6,'Juin'),(7,'Juillet'),(8,'Août'),
            (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'Décembre'),
        ],
    })


@login_required
def regle_supprimer(request, pk):
    regle = get_object_or_404(RegleRecurrence, pk=pk)
    if request.method == 'POST':
        nb = Reservation.objects.filter(regle_source=regle).count()
        regle.delete()
        messages.success(request, f"Règle supprimée ({nb} réservations conservées).")
        return redirect('administration:regles_liste')
    return render(request, 'administration/regle_supprimer.html', {'regle': regle})


# ── Regénération intelligente ─────────────────────────────────────────────────

@login_required
def regenerer_intelligent(request):
    if request.method == 'POST':
        annee     = int(request.POST.get('annee', date.today().year))
        loge_id   = request.POST.get('loge') or None
        temple_id = request.POST.get('temple') or None
        mode      = request.POST.get('mode', 'ajouter')

        regles = RegleRecurrence.objects.filter(actif=True).select_related('loge', 'temple')
        if loge_id:
            regles = regles.filter(loge_id=loge_id)
        if temple_id:
            regles = regles.filter(temple_id=temple_id)

        cree = conflit = 0
        for regle in regles:
            # Saison maçonnique : sept→déc de annee + jan→juin de annee+1
            dates_saison = [
                d for d in (
                    _calculer_dates_regle(regle, annee) +
                    _calculer_dates_regle(regle, annee + 1)
                )
                if d.month not in [7, 8]
                and not (regle.date_fin and d > regle.date_fin)
                and not (regle.date_debut and d < regle.date_debut)
            ]

            if mode == 'remplacer':
                Reservation.objects.filter(
                    regle_source=regle,
                    date__year__in=[annee, annee + 1]
                ).delete()

            for d in dates_saison:
                if Reservation.objects.filter(
                    temple=regle.temple, date=d,
                    statut__in=['validee', 'attente'],
                    heure_debut__lt=regle.heure_fin,
                    heure_fin__gt=regle.heure_debut
                ).exclude(regle_source=regle).exists():
                    conflit += 1
                    continue
                if not Reservation.objects.filter(regle_source=regle, date=d).exists():
                    Reservation.objects.create(
                        loge=regle.loge, temple=regle.temple, date=d,
                        heure_debut=regle.heure_debut, heure_fin=regle.heure_fin,
                        type_reservation='reguliere', statut='validee',
                        nom_demandeur='Generation automatique',
                        email_demandeur=regle.loge.email or settings.DEFAULT_FROM_EMAIL,
                        regle_source=regle,
                    )
                    cree += 1

        if conflit:
            messages.warning(request, f"{cree} tenues créées, {conflit} conflits ignorés.")
        else:
            messages.success(request, f"{cree} tenues créées pour la saison {annee}/{annee + 1}.")
        return redirect('administration:tableau_de_bord')

    return render(request, 'administration/regenerer.html', {
        'annees': [date.today().year, date.today().year + 1],
        'loges': Loge.objects.filter(actif=True).order_by('nom'),
        'temples': Temple.objects.all(),
    })


# ── Import Excel ──────────────────────────────────────────────────────────────

@login_required
def import_excel(request):
    errors = []
    stats  = None
    preview = None
    if request.method == 'POST' and request.FILES.get('fichier'):
        try:
            wb = openpyxl.load_workbook(request.FILES['fichier'], data_only=True)
            if 'confirmer' in request.POST:
                stats, errors = _importer_donnees(wb)
                if not errors:
                    messages.success(request, f"Import réussi : {stats['loges']} loges, {stats['regles']} règles.")
                    return redirect('administration:tableau_de_bord')
            else:
                preview = _preview_excel(wb)
        except Exception as e:
            errors.append(f"Erreur : {e}")
    return render(request, 'administration/import_excel.html', {'errors': errors, 'stats': stats, 'preview': preview})


# ── Template Excel ────────────────────────────────────────────────────────────

def _style_header(ws, row, cols, hf, hfill, ctr, thin):
    for col, h in enumerate(cols, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = hf; c.fill = hfill; c.alignment = ctr; c.border = thin

def _style_row(ws, row, vals, thin, ctr, fill=None):
    for ci, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=ci, value=v)
        c.border = thin; c.alignment = ctr
        if fill: c.fill = fill

@login_required
def telecharger_template_excel(request):
    """Template vierge avec exemples, listes déroulantes et onglet Référence."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()
    hf    = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor="0F2137")
    ex    = PatternFill("solid", fgColor="EFF6FF")   # ligne exemple
    ctr   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin  = Border(left=Side(style='thin'), right=Side(style='thin'),
                   top=Side(style='thin'), bottom=Side(style='thin'))

    # ── Onglet RÉFÉRENCE ──────────────────────────────────────────────────────
    ws_ref = wb.active
    ws_ref.title = "RÉFÉRENCE"
    _style_header(ws_ref, 1, ["Temples","Obédiences","Types loge","Rites","Jours","N° semaine","Mois (n°)","Mois (nom)"], hf, hfill, ctr, thin)
    ref_data = [
        ("Lafayette",  "GODF",   "loge",       "reaa", "Lundi",    1, 1, "Janvier"),
        ("Égalité",    "GLdF",   "haut_grade", "rer",  "Mardi",    2, 2, "Février"),
        ("Fraternité", "GLNF",   "",           "rf",   "Mercredi", 3, 3, "Mars"),
        ("Liberté",    "GLAMF",  "",           "rem",  "Jeudi",    4, 4, "Avril"),
        ("",           "GODF-RF","",           "dh",   "Vendredi",-1, 5, "Mai"),
        ("",           "",       "",           "mem",  "Samedi",   "", 6, "Juin"),
        ("",           "",       "",           "autre","Dimanche", "", 7, "Juillet"),
        ("",           "",       "",           "",     "",         "", 8, "Août"),
        ("",           "",       "",           "",     "",         "", 9, "Septembre"),
        ("",           "",       "",           "",     "",         "",10, "Octobre"),
        ("",           "",       "",           "",     "",         "",11, "Novembre"),
        ("",           "",       "",           "",     "",         "",12, "Décembre"),
    ]
    for ri, row in enumerate(ref_data, 2):
        _style_row(ws_ref, ri, row, thin, ctr)
    ws_ref.cell(row=14, column=1, value="N° semaine : 1=1re, 2=2e, 3=3e, 4=4e, -1=Dernière")
    ws_ref.cell(row=15, column=4, value="Rites : reaa, rer, rf, rem, dh, mem, autre (laisser vide si inconnu)")
    for col, w in zip(['A','B','C','D','E','F','G','H'], [14,12,12,8,12,12,10,12]):
        ws_ref.column_dimensions[col].width = w
    ws_ref.freeze_panes = "A2"

    # ── Onglet LOGES ─────────────────────────────────────────────────────────
    ws_l = wb.create_sheet("LOGES")
    headers_l = ["Abréviation *","Nom complet *","Obédience *","Type *","Rite","Email","Effectif total","Moy. agapes"]
    _style_header(ws_l, 1, headers_l, hf, hfill, ctr, thin)
    # Lignes exemple
    _style_row(ws_l, 2, ["3P","Les 3 Piliers","GODF","loge","reaa","contact@loge.fr",45,30], thin, ctr, ex)
    _style_row(ws_l, 3, ["14GO","14/Consistoire GODF","GODF","haut_grade","rf","",20,0], thin, ctr, ex)
    # Validations
    dv_obe  = DataValidation(type="list", formula1="RÉFÉRENCE!$B$2:$B$6", allow_blank=True,  showDropDown=False)
    dv_type = DataValidation(type="list", formula1='"loge,haut_grade"',   allow_blank=False, showDropDown=False)
    dv_rite = DataValidation(type="list", formula1="RÉFÉRENCE!$D$2:$D$8", allow_blank=True,  showDropDown=False)
    ws_l.add_data_validation(dv_obe);  dv_obe.sqref  = "C2:C500"
    ws_l.add_data_validation(dv_type); dv_type.sqref = "D2:D500"
    ws_l.add_data_validation(dv_rite); dv_rite.sqref = "E2:E500"
    for col, w in zip(['A','B','C','D','E','F','G','H'], [12,38,12,12,8,28,14,12]):
        ws_l.column_dimensions[col].width = w
    ws_l.freeze_panes = "A2"
    ws_l.row_dimensions[1].height = 30

    # ── Onglet RÈGLES RÉCURRENCE ─────────────────────────────────────────────
    ws_r = wb.create_sheet("RÈGLES RÉCURRENCE")
    headers_r = ["Abréviation *","Nom complet *","Obédience *","Type *",
                 "Temple *","Jour *","N° semaine *","Heure début","Heure fin",
                 "Mois actifs (ex: 9,10,11,12,1,2,3,4,5,6)"]
    _style_header(ws_r, 1, headers_r, hf, hfill, ctr, thin)
    _style_row(ws_r, 2, ["3P","Les 3 Piliers","GODF","loge","Lafayette","Dimanche",2,"19:30","22:30","9,10,11,12,1,2,3,4,5,6"], thin, ctr, ex)
    _style_row(ws_r, 3, ["14GO","14/Consistoire","GODF","haut_grade","Égalité","Lundi",1,"14:00","17:00","5,6,9,10"], thin, ctr, ex)
    # Validations
    dv_t = DataValidation(type="list", formula1="RÉFÉRENCE!$A$2:$A$5", allow_blank=False, showDropDown=False)
    dv_j = DataValidation(type="list", formula1="RÉFÉRENCE!$D$2:$D$8", allow_blank=False, showDropDown=False)
    dv_s = DataValidation(type="list", formula1="RÉFÉRENCE!$E$2:$E$6", allow_blank=False, showDropDown=False)
    ws_r.add_data_validation(dv_t); dv_t.sqref = "E2:E500"
    ws_r.add_data_validation(dv_j); dv_j.sqref = "F2:F500"
    ws_r.add_data_validation(dv_s); dv_s.sqref = "G2:G500"
    for col, w in zip(range(1, 11), [12,38,12,12,14,12,12,12,12,38]):
        ws_r.column_dimensions[get_column_letter(col)].width = w
    ws_r.freeze_panes = "A2"
    ws_r.row_dimensions[1].height = 30

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Kellermann_Import_Template.xlsx"'
    wb.save(response)
    return response


@login_required
def telecharger_export_excel(request):
    """Export des données existantes (loges + règles) au même format que le template."""
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    hf    = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor="0F2137")
    alt   = PatternFill("solid", fgColor="F8FAFC")
    ctr   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin  = Border(left=Side(style='thin'), right=Side(style='thin'),
                   top=Side(style='thin'), bottom=Side(style='thin'))

    # ── Loges ────────────────────────────────────────────────────────────────
    ws_l = wb.active
    ws_l.title = "LOGES"
    headers_l = ["Abréviation","Nom complet","Obédience","Type","Rite","Email","Effectif total","Moy. agapes"]
    _style_header(ws_l, 1, headers_l, hf, hfill, ctr, thin)
    for ri, loge in enumerate(Loge.objects.select_related('obedience').order_by('nom'), 2):
        fill = None if ri % 2 == 0 else alt
        _style_row(ws_l, ri, [
            loge.abreviation, loge.nom,
            loge.obedience.nom if loge.obedience else "",
            loge.type_loge, loge.rite or "",
            loge.email or "",
            loge.effectif_total or "", loge.effectif_moyen_agapes or "",
        ], thin, ctr, fill)
    for col, w in zip(['A','B','C','D','E','F','G','H'], [12,38,12,12,8,28,14,12]):
        ws_l.column_dimensions[col].width = w
    ws_l.freeze_panes = "A2"

    # ── Règles ───────────────────────────────────────────────────────────────
    ws_r = wb.create_sheet("RÈGLES RÉCURRENCE")
    headers_r = ["Abréviation","Nom complet","Obédience","Type",
                 "Temple","Jour","N° semaine","Heure début","Heure fin","Mois actifs"]
    _style_header(ws_r, 1, headers_r, hf, hfill, ctr, thin)
    JOURS = dict(RegleRecurrence.JOUR_CHOICES)
    for ri, reg in enumerate(RegleRecurrence.objects.select_related('loge','loge__obedience','temple').order_by('loge__nom'), 2):
        fill = None if ri % 2 == 0 else alt
        mois_str = ",".join(str(m) for m in reg.mois_actifs) if reg.mois_actifs else ""
        _style_row(ws_r, ri, [
            reg.loge.abreviation, reg.loge.nom,
            reg.loge.obedience.nom if reg.loge.obedience else "",
            reg.loge.type_loge,
            reg.temple.get_nom_display().replace("Temple ", ""),
            JOURS.get(reg.jour_semaine, ""),
            reg.numero_semaine,
            reg.heure_debut.strftime("%H:%M"),
            reg.heure_fin.strftime("%H:%M"),
            mois_str,
        ], thin, ctr, fill)
    for col, w in zip(range(1, 11), [12,38,12,12,14,12,12,12,12,30]):
        ws_r.column_dimensions[get_column_letter(col)].width = w
    ws_r.freeze_panes = "A2"

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Kellermann_Export_{date.today():%Y%m%d}.xlsx"'
    wb.save(response)
    return response


# ── Génération annuelle ───────────────────────────────────────────────────────

@login_required
def generer_reservations_annuelles(request):
    if request.method == 'POST':
        annee = int(request.POST.get('annee', date.today().year + 1))
        regles = RegleRecurrence.objects.filter(actif=True).select_related('loge', 'temple')
        created = 0
        for regle in regles:
            for d in _calculer_dates_regle(regle, annee):
                if d.month in [7, 8]:
                    continue
                if not Reservation.objects.filter(loge=regle.loge, date=d, regle_source=regle).exists():
                    Reservation.objects.create(
                        loge=regle.loge, temple=regle.temple, date=d,
                        heure_debut=regle.heure_debut, heure_fin=regle.heure_fin,
                        type_reservation='reguliere', statut='validee',
                        nom_demandeur='Generation automatique',
                        email_demandeur=regle.loge.email or settings.DEFAULT_FROM_EMAIL,
                        regle_source=regle,
                    )
                    created += 1
        messages.success(request, f"{created} réservations générées pour {annee}.")
    return redirect('administration:tableau_de_bord')


# ── Reset / Nettoyage calendrier ─────────────────────────────────────────────

@login_required
def reset_calendrier(request):
    today = date.today()
    annees = list(range(today.year - 2, today.year + 3))

    # Compteurs pour la prévisualisation
    def _compter(annee, loge_id, temple_id):
        qs_auto = Reservation.objects.filter(regle_source__isnull=False, date__year=annee)
        qs_tout = Reservation.objects.filter(date__year=annee)
        qs_regles = RegleRecurrence.objects.all()
        if loge_id:
            qs_auto  = qs_auto.filter(loge_id=loge_id)
            qs_tout  = qs_tout.filter(loge_id=loge_id)
            qs_regles = qs_regles.filter(loge_id=loge_id)
        if temple_id:
            qs_auto  = qs_auto.filter(temple_id=temple_id)
            qs_tout  = qs_tout.filter(temple_id=temple_id)
            qs_regles = qs_regles.filter(temple_id=temple_id)
        return {'auto': qs_auto.count(), 'tout': qs_tout.count(), 'regles': qs_regles.count()}

    if request.method == 'POST':
        if not request.POST.get('confirmer'):
            messages.error(request, "Cochez la case de confirmation pour valider.")
            return redirect('administration:reset_calendrier')

        action    = request.POST.get('action')
        annee     = request.POST.get('annee')
        loge_id   = request.POST.get('loge') or None
        temple_id = request.POST.get('temple') or None

        nb = 0
        if action == 'auto':
            # Supprimer réservations auto-générées pour l'année
            qs = Reservation.objects.filter(regle_source__isnull=False, date__year=int(annee))
            if loge_id:   qs = qs.filter(loge_id=loge_id)
            if temple_id: qs = qs.filter(temple_id=temple_id)
            nb, _ = qs.delete()
            messages.success(request, f"{nb} réservation(s) automatique(s) supprimée(s) pour {annee}.")

        elif action == 'tout':
            # Supprimer TOUTES les réservations temple pour l'année
            qs = Reservation.objects.filter(date__year=int(annee))
            if loge_id:   qs = qs.filter(loge_id=loge_id)
            if temple_id: qs = qs.filter(temple_id=temple_id)
            nb, _ = qs.delete()
            messages.warning(request, f"{nb} réservation(s) supprimée(s) pour {annee} (régulières + exceptionnelles).")

        elif action == 'regles':
            # Supprimer les règles de récurrence (+ réservations liées en cascade si souhaité)
            qs = RegleRecurrence.objects.all()
            if loge_id:   qs = qs.filter(loge_id=loge_id)
            if temple_id: qs = qs.filter(temple_id=temple_id)
            nb, _ = qs.delete()
            messages.warning(request, f"{nb} règle(s) de récurrence supprimée(s).")

        elif action == 'tout_absolu':
            # Tout supprimer : règles + réservations sans filtre année
            qs_r = Reservation.objects.all()
            qs_reg = RegleRecurrence.objects.all()
            if loge_id:
                qs_r   = qs_r.filter(loge_id=loge_id)
                qs_reg = qs_reg.filter(loge_id=loge_id)
            if temple_id:
                qs_r   = qs_r.filter(temple_id=temple_id)
                qs_reg = qs_reg.filter(temple_id=temple_id)
            nb_r, _ = qs_r.delete()
            nb_reg, _ = qs_reg.delete()
            messages.error(request, f"Nettoyage complet : {nb_reg} règle(s) et {nb_r} réservation(s) supprimée(s).")

        return redirect('administration:tableau_de_bord')

    # GET — afficher les compteurs
    annee_sel  = int(request.GET.get('annee', today.year))
    loge_id    = request.GET.get('loge') or None
    temple_id  = request.GET.get('temple') or None
    compteurs  = _compter(annee_sel, loge_id, temple_id)

    return render(request, 'administration/reset_calendrier.html', {
        'annees'   : annees,
        'annee_sel': annee_sel,
        'loges'    : Loge.objects.filter(actif=True).order_by('nom'),
        'temples'  : Temple.objects.all(),
        'loge_id'  : loge_id,
        'temple_id': temple_id,
        'compteurs': compteurs,
    })


# ── Gestion saison ────────────────────────────────────────────────────────────

@login_required
def gestion_saison(request):
    # Statistiques par saison
    current_year = date.today().year
    saisons = []
    for annee in range(current_year - 2, current_year + 3):
        saison_debut = date(annee, 9, 1)
        saison_fin = date(annee + 1, 6, 30)

        auto = Reservation.objects.filter(
            regle_source__isnull=False,
            date__gte=saison_debut,
            date__lte=saison_fin
        ).count()

        manuel = Reservation.objects.filter(
            regle_source__isnull=True,
            date__gte=saison_debut,
            date__lte=saison_fin
        ).count()

        saisons.append({
            'annee': annee,
            'auto': auto,
            'manuel': manuel,
            'total': auto + manuel
        })

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'supprimer_saison':
            annee = int(request.POST.get('annee'))
            saison_debut = date(annee, 9, 1)
            saison_fin = date(annee + 1, 6, 30)

            # Supprimer UNIQUEMENT les réservations automatiques
            deleted = Reservation.objects.filter(
                regle_source__isnull=False,
                date__gte=saison_debut,
                date__lte=saison_fin
            ).delete()[0]

            messages.success(request, f"Saison {annee}-{annee+1} : {deleted} réservations automatiques supprimées.")
            return redirect('administration:gestion_saison')

        elif action == 'generer_saison':
            annee = int(request.POST.get('annee_cible'))

            # Utiliser la fonction de régénération intelligente existante
            regles = RegleRecurrence.objects.filter(actif=True).select_related('loge', 'temple')
            cree = conflit = 0

            for regle in regles:
                for d in _calculer_dates_regle(regle, annee):
                    if d.month in [7, 8]:  # Éviter juillet-août
                        continue
                    if regle.date_fin and d > regle.date_fin:
                        continue
                    if regle.date_debut and d < regle.date_debut:
                        continue

                    # Supprimer les anciennes réservations automatiques pour cette règle/date
                    Reservation.objects.filter(regle_source=regle, date=d).delete()

                    # Vérifier conflits avec réservations manuelles
                    if Reservation.objects.filter(
                        temple=regle.temple, date=d, statut__in=['validee','attente'],
                        heure_debut__lt=regle.heure_fin, heure_fin__gt=regle.heure_debut
                    ).exclude(regle_source=regle).exists():
                        conflit += 1
                        continue

                    # Créer la nouvelle réservation
                    Reservation.objects.create(
                        loge=regle.loge, temple=regle.temple, date=d,
                        heure_debut=regle.heure_debut, heure_fin=regle.heure_fin,
                        type_reservation='reguliere', statut='validee',
                        nom_demandeur='Generation automatique',
                        email_demandeur=regle.loge.email or settings.DEFAULT_FROM_EMAIL,
                        regle_source=regle,
                    )
                    cree += 1

            if conflit:
                messages.warning(request, f"Saison {annee} : {cree} tenues créées, {conflit} conflits ignorés.")
            else:
                messages.success(request, f"Saison {annee} : {cree} tenues créées.")
            return redirect('administration:gestion_saison')

        elif action == 'reset_complet':
            confirmation = request.POST.get('confirmation', '').strip()
            if confirmation != 'CONFIRMER':
                messages.error(request, "Veuillez saisir 'CONFIRMER' pour valider la suppression.")
                return redirect('administration:gestion_saison')

            # Supprimer TOUTES les réservations automatiques
            deleted = Reservation.objects.filter(regle_source__isnull=False).delete()[0]
            messages.success(request, f"Reset complet : {deleted} réservations automatiques supprimées.")
            return redirect('administration:gestion_saison')

        elif action == 'backup':
            return telecharger_backup(request)

    return render(request, 'administration/gestion_saison.html', {
        'saisons': saisons,
        'current_year': current_year,
        'annees': list(range(current_year - 1, current_year + 4)),
        'db_last_modified': _get_db_last_modified(),
    })


@login_required
def telecharger_backup(request):
    """Télécharge la base de données SQLite en tant que sauvegarde."""
    import os
    from django.conf import settings

    # Chemin vers la base de données
    db_path = settings.DATABASES['default']['NAME']

    # Vérifier que le fichier existe
    if not os.path.exists(db_path):
        messages.error(request, "Fichier de base de données introuvable.")
        return redirect('administration:gestion_saison')

    # Nom du fichier de téléchargement
    today = date.today().strftime('%Y%m%d')
    filename = f'backup_kellermann_{today}.sqlite3'

    # Lire le fichier et le retourner en réponse
    with open(db_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@login_required
def restaurer_backup(request):
    """Permet de restaurer une sauvegarde de la base de données."""
    import os
    import sqlite3
    from django.conf import settings

    if request.method == 'POST' and request.FILES.get('backup_file'):
        backup_file = request.FILES['backup_file']

        # Vérifier l'extension du fichier
        if not backup_file.name.endswith('.sqlite3'):
            messages.error(request, "Le fichier doit avoir l'extension .sqlite3")
            return redirect('administration:restaurer_backup')

        # Vérifier que c'est bien une base SQLite valide
        try:
            # Tester la connexion à la base uploadée
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in backup_file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            # Tester la validité du fichier SQLite
            conn = sqlite3.connect(temp_path)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            conn.close()

        except Exception as e:
            os.unlink(temp_path)
            messages.error(request, f"Fichier SQLite invalide : {e}")
            return redirect('administration:restaurer_backup')

        # Chemin de la base actuelle
        db_path = settings.DATABASES['default']['NAME']

        # Créer une sauvegarde automatique de la base actuelle
        backup_path = f"{db_path}.avant_restauration"
        try:
            import shutil
            shutil.copy2(db_path, backup_path)
        except Exception as e:
            messages.warning(request, f"Impossible de créer la sauvegarde automatique : {e}")

        # Remplacer la base actuelle par le fichier uploadé
        try:
            shutil.move(temp_path, db_path)
            messages.success(request, "Sauvegarde restaurée avec succès. Une copie de l'ancienne base a été sauvegardée.")
            return redirect('administration:gestion_saison')
        except Exception as e:
            messages.error(request, f"Erreur lors de la restauration : {e}")
            return redirect('administration:restaurer_backup')

    return render(request, 'administration/restaurer_backup.html')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db_last_modified():
    """Retourne la date de dernière modification de la base de données."""
    import os
    from django.conf import settings

    db_path = settings.DATABASES['default']['NAME']
    if os.path.exists(db_path):
        timestamp = os.path.getmtime(db_path)
        return date.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')
    return "Inconnue"


def _preview_excel(wb):
    preview = {}
    for sheet_name in wb.sheetnames[:4]:
        ws = wb[sheet_name]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 6: break
            if any(v is not None for v in row):
                rows.append([str(v)[:40] if v is not None else '' for v in row[:10]])
        preview[sheet_name] = rows
    return preview


def _importer_donnees(wb):
    errors = []
    stats  = {'loges': 0, 'obediences': 0, 'regles': 0}

    if 'LOGES' in wb.sheetnames:
        for i, row in enumerate(wb['LOGES'].iter_rows(min_row=2, values_only=True), 2):
            try:
                if not row[0]: continue
                ob, co = Obedience.objects.get_or_create(nom=str(row[2]).strip() if row[2] else 'Non définie')
                if co: stats['obediences'] += 1
                RITES_VALIDES = ['reaa','rer','rf','rf_reaa','rem','dh','mem','rapmm','rmfr','emulation','marque','autre']
                RITE_ALIASES  = {'rf/reaa': 'rf_reaa', 'reaa/rf': 'rf_reaa'}
                def _normalise_rite(raw):
                    r = raw.strip().lower()
                    return RITE_ALIASES.get(r, r if r in RITES_VALIDES else '')
                # Nouveau format : col4=rite, col5=email, col6=effectif, col7=agapes
                # Ancien format  : col4=email, col5=effectif, col6=agapes, col7=rite
                # Détection : si col4 est dans les rites valides → nouveau format
                col4_val = str(row[4]).strip().lower() if len(row) > 4 and row[4] else ''
                col4_norm = RITE_ALIASES.get(col4_val, col4_val)
                nouveau_format = col4_norm in RITES_VALIDES or col4_val == ''
                if nouveau_format:
                    rite     = _normalise_rite(str(row[4]) if len(row) > 4 and row[4] else '')
                    email    = str(row[5]).strip() if len(row) > 5 and row[5] else ''
                    effectif = int(row[6]) if len(row) > 6 and row[6] and str(row[6]).isdigit() else 0
                    agapes   = int(row[7]) if len(row) > 7 and row[7] and str(row[7]).isdigit() else 0
                else:
                    email    = col4_val
                    effectif = int(row[5]) if len(row) > 5 and row[5] and str(row[5]).isdigit() else 0
                    agapes   = int(row[6]) if len(row) > 6 and row[6] and str(row[6]).isdigit() else 0
                    rite     = _normalise_rite(str(row[7]) if len(row) > 7 and row[7] else '')
                _, cl = Loge.objects.update_or_create(
                    abreviation=str(row[0]).strip(),
                    defaults={'nom': str(row[1]).strip() if row[1] else str(row[0]).strip(), 'obedience': ob,
                              'type_loge': str(row[3]).strip() if row[3] in ('loge','haut_grade') else 'loge',
                              'rite': rite, 'email': email,
                              'effectif_total': effectif, 'effectif_moyen_agapes': agapes}
                )
                if cl: stats['loges'] += 1
            except Exception as e:
                errors.append(f"LOGES ligne {i} : {e}")

    # Accepter l'ancien nom sans accents et le nouveau avec accents
    regles_sheet = next((n for n in wb.sheetnames if 'GLES' in n and 'CURRENCE' in n), None)
    if regles_sheet:
        JOURS  = {'Lundi':0,'Mardi':1,'Mercredi':2,'Jeudi':3,'Vendredi':4,'Samedi':5,'Dimanche':6}
        TEMPLES = {'Lafayette':'lafayette','Liberte':'liberte','Egalite':'egalite','Fraternite':'fraternite',
                   'Égalité':'egalite','Fraternité':'fraternite','Liberté':'liberte'}
        for i, row in enumerate(wb[regles_sheet].iter_rows(min_row=2, values_only=True), 2):
            try:
                if not row[0] or not row[4] or not row[5] or row[6] is None: continue
                try: loge = Loge.objects.get(abreviation=str(row[0]).strip())
                except Loge.DoesNotExist: errors.append(f"REGLES ligne {i} : loge '{row[0]}' introuvable"); continue
                tk = TEMPLES.get(str(row[4]).strip())
                if not tk: errors.append(f"REGLES ligne {i} : temple '{row[4]}' inconnu"); continue
                try: temple = Temple.objects.get(nom=tk)
                except Temple.DoesNotExist: errors.append(f"REGLES ligne {i} : temple absent"); continue
                jn = JOURS.get(str(row[5]).strip())
                if jn is None: errors.append(f"REGLES ligne {i} : jour '{row[5]}' inconnu"); continue
                _, cr = RegleRecurrence.objects.get_or_create(
                    loge=loge, temple=temple, jour_semaine=jn, numero_semaine=int(row[6]),
                    defaults={'heure_debut': str(row[7]) if len(row)>7 and row[7] else '19:30',
                              'heure_fin': str(row[8]) if len(row)>8 and row[8] else '22:30', 'actif': True}
                )
                if cr: stats['regles'] += 1
            except Exception as e:
                errors.append(f"REGLES ligne {i} : {e}")

    return stats, errors


def _calculer_dates_regle(regle, annee):
    mois_list = regle.mois_actifs if regle.mois_actifs else list(range(1, 13))
    return [d for mois in mois_list for d in [_nieme_jour_du_mois(annee, mois, regle.numero_semaine, regle.jour_semaine)] if d]


# ── Paramètres ────────────────────────────────────────────────────────────────

@login_required
def parametres(request):
    params = Parametres.get_instance()
    if request.method == 'POST':
        params.mot_de_passe_annuel = request.POST.get('mot_de_passe_annuel', params.mot_de_passe_annuel)
        params.email_admin = request.POST.get('email_admin', params.email_admin)
        params.email_from = request.POST.get('email_from', params.email_from)
        params.smtp_host = request.POST.get('smtp_host', params.smtp_host)
        params.smtp_port = int(request.POST.get('smtp_port', params.smtp_port))
        params.smtp_user = request.POST.get('smtp_user', params.smtp_user)
        params.smtp_password = request.POST.get('smtp_password', params.smtp_password)
        params.smtp_tls = request.POST.get('smtp_tls') == 'on'
        params.save()
        messages.success(request, "Paramètres sauvegardés.")
        return redirect('administration:parametres')
    return render(request, 'administration/parametres.html', {'params': params})


@login_required
def tester_smtp(request):
    if request.method != 'POST':
        return redirect('administration:parametres')
    dest = get_email_admin()
    try:
        send_mail_kellermann(
            subject="[Kellermann] Test SMTP",
            message=(
                "Cet email confirme que la configuration SMTP est fonctionnelle.\n\n"
                "Si vous recevez ce message, les paramètres SMTP sont correctement configurés."
            ),
            recipient_list=[dest],
            fail_silently=False,
        )
        messages.success(request, f"Email de test envoyé avec succès à {dest}.")
    except Exception as e:
        messages.error(request, f"Échec de l'envoi : {e}")
    return redirect('administration:parametres')


# ── Gestion des salles ────────────────────────────────────────────────────────

@login_required
def salles_liste(request):
    salles = SalleReunion.objects.all().order_by('nom')
    return render(request, 'administration/salles_liste.html', {
        'salles': salles,
        'nb_salles': salles.count(),
    })


@login_required
def salle_form(request, pk=None):
    salle = get_object_or_404(SalleReunion, pk=pk) if pk else None
    if request.method == 'POST':
        try:
            data = {
                'nom': request.POST['nom'],
                'type_salle': request.POST['type_salle'],
                'capacite': int(request.POST['capacite']),
                'description': request.POST.get('description', '').strip(),
                'actif': request.POST.get('actif') == 'on',
            }
            if salle:
                for k, v in data.items():
                    setattr(salle, k, v)
                salle.save()
                messages.success(request, "Salle modifiée.")
            else:
                SalleReunion.objects.create(**data)
                messages.success(request, "Salle ajoutée.")
            return redirect('administration:salles_liste')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'administration/salle_form.html', {
        'salle': salle,
        'type_choices': SalleReunion.TYPE_CHOICES,
    })


@login_required
def salle_supprimer(request, pk):
    salle = get_object_or_404(SalleReunion, pk=pk)
    if request.method == 'POST':
        salle.delete()
        messages.success(request, "Salle supprimée.")
        return redirect('administration:salles_liste')
    return render(request, 'administration/salle_supprimer.html', {'salle': salle})


@login_required
def agapes_traiteur(request):
    """Vue synthétique agapes + banquets pour le traiteur."""
    today = date.today()
    annee_courante = today.year if today.month >= 9 else today.year - 1
    annee_param = int(request.GET.get('annee', annee_courante))
    debut_saison = date(annee_param, 9, 1)
    fin_saison   = date(annee_param + 1, 6, 30)

    # Tenues avec agapes
    tenues = (
        Reservation.objects
        .select_related('loge', 'temple')
        .filter(
            besoin_agapes=True,
            statut='validee',
            date__gte=debut_saison,
            date__lte=fin_saison,
        )
        .order_by('date')
    )

    # Banquets (ReservationSalle type agapes)
    banquets = (
        ReservationSalle.objects
        .select_related('salle')
        .filter(
            salle__type_salle='agapes',
            statut='validee',
            date__gte=debut_saison,
            date__lte=fin_saison,
        )
        .order_by('date')
    )

    # Fusion en liste normalisée
    lignes = []
    for t in tenues:
        lignes.append({
            'date':         t.date,
            'organisation': t.loge.nom if t.loge else (t.nom_organisation or t.nom_demandeur),
            'type':         'Tenue + agapes',
            'couverts':     t.nombre_repas,
            'lieu':         str(t.temple),
            'horaires':     f"{t.heure_debut:%H:%M} – {t.heure_fin:%H:%M}",
            'commentaire':  t.commentaire,
        })
    for b in banquets:
        lignes.append({
            'date':         b.date,
            'organisation': b.organisation or b.nom_demandeur,
            'type':         'Banquet d\'ordre',
            'couverts':     b.nombre_participants,
            'lieu':         str(b.salle),
            'horaires':     f"{b.heure_debut:%H:%M} – {b.heure_fin:%H:%M}",
            'commentaire':  b.commentaire,
        })
    lignes.sort(key=lambda x: x['date'])

    # Totaux par mois
    MOIS_ORDRE = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
    MOIS_NOMS  = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                  9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}
    totaux_mois = {}
    for m in MOIS_ORDRE:
        sous_liste = [l for l in lignes if l['date'].month == m]
        if sous_liste:
            totaux_mois[m] = {
                'nom':      MOIS_NOMS[m],
                'lignes':   sous_liste,
                'total':    sum(l['couverts'] for l in sous_liste),
            }

    context = {
        'lignes':       lignes,
        'totaux_mois':  totaux_mois,
        'total_saison': sum(l['couverts'] for l in lignes),
        'annee':        annee_param,
        'annees':       list(range(annee_courante - 2, annee_courante + 2)),
        'saison_label': f"{annee_param}/{annee_param + 1}",
        'mois_liste':   [(m, MOIS_NOMS[m]) for m in MOIS_ORDRE],
    }
    return render(request, 'administration/agapes_traiteur.html', context)


@login_required
def agapes_export_excel(request):
    """Export Excel de la synthèse agapes/banquets."""
    today = date.today()
    annee_courante = today.year if today.month >= 9 else today.year - 1
    annee_param = int(request.GET.get('annee', annee_courante))
    debut_saison = date(annee_param, 9, 1)
    fin_saison   = date(annee_param + 1, 6, 30)

    tenues = (
        Reservation.objects
        .select_related('loge', 'temple')
        .filter(besoin_agapes=True, statut='validee',
                date__gte=debut_saison, date__lte=fin_saison)
        .order_by('date')
    )
    banquets = (
        ReservationSalle.objects
        .select_related('salle')
        .filter(salle__type_salle='agapes', statut='validee',
                date__gte=debut_saison, date__lte=fin_saison)
        .order_by('date')
    )

    lignes = []
    for t in tenues:
        lignes.append((
            t.date.strftime('%d/%m/%Y'),
            t.loge.nom if t.loge else (t.nom_organisation or t.nom_demandeur),
            'Tenue + agapes',
            t.nombre_repas,
            str(t.temple),
            f"{t.heure_debut:%H:%M} – {t.heure_fin:%H:%M}",
            t.commentaire,
        ))
    for b in banquets:
        lignes.append((
            b.date.strftime('%d/%m/%Y'),
            b.organisation or b.nom_demandeur,
            "Banquet d'ordre",
            b.nombre_participants,
            str(b.salle),
            f"{b.heure_debut:%H:%M} – {b.heure_fin:%H:%M}",
            b.commentaire,
        ))
    lignes.sort(key=lambda x: x[0])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Agapes {annee_param}-{annee_param + 1}"

    # Styles
    hf    = Font(bold=True, color="C8A84B")
    hfill = PatternFill("solid", fgColor="0F2137")
    ctr   = Alignment(horizontal="center", vertical="center")
    thin  = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    total_fill = PatternFill("solid", fgColor="F1F5F9")
    total_font = Font(bold=True)

    headers = ["Date", "Loge / Organisation", "Type", "Couverts", "Lieu", "Horaires", "Commentaire"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = hf; cell.fill = hfill; cell.alignment = ctr; cell.border = thin
    ws.row_dimensions[1].height = 20

    col_widths = [14, 36, 20, 12, 22, 18, 40]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    MOIS_NOMS = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                 9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}
    MOIS_ORDRE = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]

    row_idx = 2
    for mois in MOIS_ORDRE:
        mois_lignes = [l for l in lignes if l[0][3:5] == f"{mois:02d}"]
        if not mois_lignes:
            continue
        # Séparateur de mois
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=7)
        sep = ws.cell(row=row_idx, column=1, value=MOIS_NOMS[mois].upper())
        sep.font = Font(bold=True, color="0F2137")
        sep.fill = PatternFill("solid", fgColor="E2E8F0")
        sep.alignment = ctr; sep.border = thin
        row_idx += 1
        # Lignes
        for l in mois_lignes:
            for col, val in enumerate(l, 1):
                c = ws.cell(row=row_idx, column=col, value=val)
                c.border = thin
                if col == 4:  # Couverts
                    c.alignment = ctr
            row_idx += 1
        # Total mois
        total = sum(l[3] for l in mois_lignes)
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=3)
        ws.cell(row=row_idx, column=1, value=f"Total {MOIS_NOMS[mois]}").font = total_font
        ws.cell(row=row_idx, column=1).fill = total_fill
        ws.cell(row=row_idx, column=1).border = thin
        tc = ws.cell(row=row_idx, column=4, value=total)
        tc.font = total_font; tc.fill = total_fill
        tc.alignment = ctr; tc.border = thin
        for col in range(5, 8):
            ws.cell(row=row_idx, column=col).fill = total_fill
            ws.cell(row=row_idx, column=col).border = thin
        row_idx += 1

    # Total saison
    total_saison = sum(l[3] for l in lignes)
    row_idx += 1
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=3)
    ws.cell(row=row_idx, column=1, value=f"TOTAL SAISON {annee_param}/{annee_param+1}").font = Font(bold=True, color="C8A84B")
    ws.cell(row=row_idx, column=1).fill = PatternFill("solid", fgColor="0F2137")
    ws.cell(row=row_idx, column=1).border = thin
    ts = ws.cell(row=row_idx, column=4, value=total_saison)
    ts.font = Font(bold=True, color="C8A84B")
    ts.fill = PatternFill("solid", fgColor="0F2137")
    ts.alignment = ctr; ts.border = thin

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="agapes_{annee_param}-{annee_param+1}.xlsx"'
    wb.save(response)
    return response


@login_required
def agapes_export_pdf(request):
    """Export PDF de la synthèse agapes/banquets (mensuel ou 7 jours)."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    today = date.today()
    annee_courante = today.year if today.month >= 9 else today.year - 1
    annee_param = int(request.GET.get('annee', annee_courante))
    periode = request.GET.get('periode', 'mensuel')
    mois_param = request.GET.get('mois')

    MOIS_NOMS = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                 7:'Juillet',8:'Août',9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}
    JOURS_FR  = {0:'Lun',1:'Mar',2:'Mer',3:'Jeu',4:'Ven',5:'Sam',6:'Dim'}

    if periode == 'hebdo':
        date_debut = today
        date_fin   = today + timedelta(days=6)
        titre_periode = f"7 prochains jours ({date_debut.strftime('%d/%m')} – {date_fin.strftime('%d/%m/%Y')})"
        nom_fichier = f"agapes_7jours_{today.strftime('%Y%m%d')}.pdf"
    else:
        if mois_param:
            mois_int = int(mois_param)
        else:
            mois_int = today.month
        annee_mois = annee_param if mois_int >= 9 else annee_param + 1
        import calendar as _cal
        dernier_jour = _cal.monthrange(annee_mois, mois_int)[1]
        date_debut = date(annee_mois, mois_int, 1)
        date_fin   = date(annee_mois, mois_int, dernier_jour)
        titre_periode = f"{MOIS_NOMS[mois_int]} {annee_mois}"
        nom_fichier = f"agapes_{annee_mois}_{mois_int:02d}.pdf"

    # Requêtes
    tenues = (
        Reservation.objects
        .select_related('loge', 'temple')
        .filter(besoin_agapes=True, statut='validee',
                date__gte=date_debut, date__lte=date_fin)
        .order_by('date')
    )
    banquets = (
        ReservationSalle.objects
        .select_related('salle')
        .filter(salle__type_salle='agapes', statut='validee',
                date__gte=date_debut, date__lte=date_fin)
        .order_by('date')
    )

    lignes = []
    for t in tenues:
        lignes.append({
            'date':         t.date,
            'organisation': t.loge.nom if t.loge else (t.nom_organisation or t.nom_demandeur),
            'type':         'Tenue + agapes',
            'couverts':     t.nombre_repas,
            'lieu':         str(t.temple),
            'horaires':     f"{t.heure_debut:%H:%M}–{t.heure_fin:%H:%M}",
        })
    for b in banquets:
        lignes.append({
            'date':         b.date,
            'organisation': b.organisation or b.nom_demandeur,
            'type':         "Banquet d'ordre",
            'couverts':     b.nombre_participants,
            'lieu':         str(b.salle),
            'horaires':     f"{b.heure_debut:%H:%M}–{b.heure_fin:%H:%M}",
        })
    lignes.sort(key=lambda x: x['date'])

    # Couleurs
    C_NAVY  = colors.HexColor('#0F2137')
    C_GOLD  = colors.HexColor('#C8A84B')
    C_LIGHT = colors.HexColor('#F8FAFC')
    C_TOTAL = colors.HexColor('#E2E8F0')

    # Construction du PDF
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
    )

    sty_titre = ParagraphStyle('titre', fontSize=16, textColor=C_NAVY,
                               spaceAfter=4, fontName='Helvetica-Bold')
    sty_sous  = ParagraphStyle('sous',  fontSize=11, textColor=C_GOLD,
                               spaceAfter=12, fontName='Helvetica-Bold')
    sty_pied  = ParagraphStyle('pied',  fontSize=8,  textColor=colors.grey,
                               alignment=TA_CENTER)

    story = []

    # En-tête
    story.append(Paragraph("Kellermann — Recapitulatif Agapes", sty_titre))
    story.append(Paragraph(titre_periode, sty_sous))

    if not lignes:
        story.append(Paragraph("Aucun evenement sur cette periode.", ParagraphStyle('x', fontSize=10)))
    else:
        # Tableau
        headers = ["Date", "Loge / Organisation", "Type", "Couverts", "Lieu", "Horaires"]
        col_widths = [2.5*cm, 5.5*cm, 3.2*cm, 2*cm, 3.2*cm, 2.6*cm]

        table_data = [headers]
        for l in lignes:
            jour_fr = JOURS_FR.get(l['date'].weekday(), '')
            table_data.append([
                f"{jour_fr} {l['date'].strftime('%d/%m/%Y')}",
                l['organisation'],
                l['type'],
                str(l['couverts']),
                l['lieu'],
                l['horaires'],
            ])

        # Ligne total
        total = sum(l['couverts'] for l in lignes)
        table_data.append(["", "TOTAL", "", str(total), "", ""])

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

        n = len(table_data)
        style = TableStyle([
            # En-tête
            ('BACKGROUND',   (0,0), (-1,0),  C_NAVY),
            ('TEXTCOLOR',    (0,0), (-1,0),  C_GOLD),
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0),  8),
            ('ALIGN',        (0,0), (-1,0),  'CENTER'),
            ('BOTTOMPADDING',(0,0), (-1,0),  6),
            ('TOPPADDING',   (0,0), (-1,0),  6),
            # Corps
            ('FONTNAME',     (0,1), (-1,n-2), 'Helvetica'),
            ('FONTSIZE',     (0,1), (-1,n-2), 8),
            ('ROWBACKGROUNDS',(0,1),(-1,n-2), [colors.white, C_LIGHT]),
            ('ALIGN',        (3,1), (3,n-2),  'CENTER'),
            ('FONTNAME',     (3,1), (3,n-2),  'Helvetica-Bold'),
            # Ligne total
            ('BACKGROUND',   (0,n-1), (-1,n-1), C_TOTAL),
            ('FONTNAME',     (0,n-1), (-1,n-1), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,n-1), (-1,n-1), 9),
            ('ALIGN',        (1,n-1), (1,n-1),  'RIGHT'),
            ('ALIGN',        (3,n-1), (3,n-1),  'CENTER'),
            ('TEXTCOLOR',    (0,n-1), (-1,n-1), C_NAVY),
            ('TOPPADDING',   (0,n-1), (-1,n-1), 6),
            ('BOTTOMPADDING',(0,n-1), (-1,n-1), 6),
            # Bordures
            ('GRID',         (0,0),  (-1,-1),  0.4, colors.HexColor('#CBD5E1')),
            ('BOX',          (0,0),  (-1,-1),  1,   C_NAVY),
        ])
        tbl.setStyle(style)
        story.append(tbl)
        story.append(Spacer(1, 0.5*cm))

    # Pied de page
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Document genere le {today.strftime('%d/%m/%Y')} — Temples Kellermann",
        sty_pied,
    ))

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


def _nieme_jour_du_mois(annee, mois, n, jour):
    premier = date(annee, mois, 1)
    dernier = date(annee, mois, calendar.monthrange(annee, mois)[1])
    if n > 0:
        delta = (jour - premier.weekday()) % 7
        cible = premier + timedelta(days=delta + (n - 1) * 7)
        return cible if cible.month == mois else None
    else:
        delta = (dernier.weekday() - jour) % 7
        cible = dernier - timedelta(days=delta)
        return cible if cible.month == mois else None
