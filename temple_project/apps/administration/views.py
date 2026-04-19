from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin, get_email_traiteur
from django.http import HttpResponse
from datetime import date, timedelta
import calendar
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from temple_project.apps.reservations.models import (
    Reservation, RegleRecurrence, Temple, SalleReunion, ReservationSalle,
    DemandeAccesPortail, ValidationSaison, ValidationSaisonLigne,
)
from temple_project.apps.loges.models import Loge, Obedience
from .models import Parametres, JournalEvenement
from .journal import log_evenement


# ── Tableau de bord ───────────────────────────────────────────────────────────

@login_required
def tableau_de_bord(request):
    reservations_attente  = Reservation.objects.filter(statut='attente').select_related('loge', 'temple').order_by('date')
    reservations_recentes = Reservation.objects.order_by('-created_at')[:10]
    reservations_salle_attente = ReservationSalle.objects.filter(
        statut='attente'
    ).select_related('salle').order_by('date')
    demandes_portail_attente = DemandeAccesPortail.objects.filter(statut='attente').order_by('created_at')
    context = {
        'attente':                  reservations_attente,
        'recentes':                 reservations_recentes,
        'nb_attente':               reservations_attente.count(),
        'nb_loges':                 Loge.objects.count(),
        'nb_reservations':          Reservation.objects.count(),
        'nb_regles':                RegleRecurrence.objects.filter(actif=True).count(),
        'attente_salles':           reservations_salle_attente,
        'nb_attente_salles':        reservations_salle_attente.count(),
        'demandes_portail':         demandes_portail_attente,
        'nb_demandes_portail':      demandes_portail_attente.count(),
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
            log_evenement('validation_reservation',
                f"Réservation validée : {resa.loge} — {resa.date:%d/%m/%Y} {resa.heure_debut:%H:%M}–{resa.heure_fin:%H:%M} ({resa.temple})",
                request=request, objet=resa)
        else:
            messages.warning(request, f"Demande de {resa.loge} refusée — email envoyé à {resa.email_demandeur}.")
            log_evenement('refus_reservation',
                f"Réservation refusée : {resa.loge} — {resa.date:%d/%m/%Y} {resa.heure_debut:%H:%M}–{resa.heure_fin:%H:%M} ({resa.temple})",
                request=request, objet=resa)

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
            log_evenement('validation_reservation',
                f"Réservation salle validée : {resa.organisation} — {resa.date:%d/%m/%Y} {resa.heure_debut:%H:%M}–{resa.heure_fin:%H:%M} ({resa.salle})",
                request=request, objet=resa)
        else:
            messages.warning(request, f"Demande de salle pour {resa.organisation} refusée — email envoyé à {resa.email_demandeur}.")
            log_evenement('refus_reservation',
                f"Réservation salle refusée : {resa.organisation} — {resa.date:%d/%m/%Y} {resa.heure_debut:%H:%M}–{resa.heure_fin:%H:%M} ({resa.salle})",
                request=request, objet=resa)

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
        f"[Kellermann] Votre demande du {resa.date:%d/%m/%Y} a été validée"
        if validee else
        f"[Kellermann] Votre demande du {resa.date:%d/%m/%Y} n'a pas pu être accordée"
    )
    corps = f"""Bonjour {resa.nom_demandeur},

{"Votre demande de réservation a été validée." if validee else "Votre demande de réservation n'a pas pu être acceptée."}

Détails :
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
        destinataires = [resa.email_demandeur]
        # CC traiteur si agapes validée
        if resa.besoin_agapes and action == 'valider':
            email_t = get_email_traiteur()
            if email_t:
                destinataires.append(email_t)
        send_mail_kellermann(sujet, corps, destinataires, fail_silently=False)
    except Exception as e:
        print(f"Erreur email décision : {e}")


@login_required
def valider_acces_portail(request, pk):
    demande = get_object_or_404(DemandeAccesPortail, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('valider', 'refuser'):
            messages.error(request, "Action invalide.")
            return redirect('administration:tableau_de_bord')

        demande.statut = 'validee' if action == 'valider' else 'refusee'
        demande.save()

        if action == 'valider':
            lien = request.build_absolute_uri(f'/reservations/portail/{demande.token}/')
            send_mail_kellermann(
                subject="[Kellermann] Votre accès au portail loge a été validé",
                message=(
                    f"Bonjour {demande.nom_venerable},\n\n"
                    f"Votre demande d'accès au portail loge a été validée.\n\n"
                    f"Vous pouvez accéder à votre espace loge via le lien suivant :\n"
                    f"{lien}\n\n"
                    f"Ce lien est personnel — ne le partagez pas.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[demande.email],
            )
            messages.success(request, f"Accès validé pour {demande.nom_loge_display()} — lien envoyé à {demande.email}.")
        else:
            send_mail_kellermann(
                subject="[Kellermann] Votre demande d'accès portail",
                message=(
                    f"Bonjour {demande.nom_venerable},\n\n"
                    f"Votre demande d'accès au portail loge n'a pas pu être accordée.\n\n"
                    f"Pour toute question, contactez l'administration.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[demande.email],
            )
            messages.warning(request, f"Demande refusée pour {demande.nom_loge_display()}.")

        return redirect('administration:tableau_de_bord')

    return render(request, 'administration/valider_acces_portail.html', {'demande': demande})


def _envoyer_email_decision_salle(resa, action, commentaire_admin=''):
    validee = (action == 'valider')
    is_cabinet = resa.salle.type_salle == 'cabinet_reflexion'

    if is_cabinet:
        sujet = (
            f"[Kellermann] Votre demande de cabinet du {resa.date:%d/%m/%Y} a été validée"
            if validee else
            f"[Kellermann] Votre demande de cabinet du {resa.date:%d/%m/%Y} n'a pas pu être accordée"
        )
        if validee:
            corps = f"""Bonjour {resa.nom_demandeur},

Votre demande de cabinet de réflexion a été validée.

Cabinet attribué : {resa.salle.nom}
Date             : {resa.date:%d/%m/%Y}
Horaires         : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
Objet            : {resa.objet}
"""
        else:
            corps = f"""Bonjour {resa.nom_demandeur},

Votre demande de cabinet de réflexion du {resa.date:%d/%m/%Y} n'a pas pu être accordée.

Date     : {resa.date:%d/%m/%Y}
Horaires : {resa.heure_debut:%H:%M} - {resa.heure_fin:%H:%M}
Objet    : {resa.objet}
"""
    else:
        sujet = (
            f"[Kellermann] Votre demande de salle du {resa.date:%d/%m/%Y} a été validée"
            if validee else
            f"[Kellermann] Votre demande de salle du {resa.date:%d/%m/%Y} n'a pas pu être accordée"
        )
        corps = f"""Bonjour {resa.nom_demandeur},

{"Votre demande de réservation de salle a été validée." if validee else "Votre demande de réservation de salle n'a pas pu être acceptée."}

Détails :
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
                    log_evenement('import_excel',
                        f"Import Excel réussi : {stats['loges']} loge(s), {stats['regles']} règle(s) importée(s)",
                        request=request, objet_type='systeme')
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

_JOURS_FR = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def _dates_saison(regle, annee):
    """
    Retourne toutes les dates de la règle dans la saison annee → annee+1
    (01/09/annee → 30/06/annee+1), en respectant date_debut/date_fin de la règle.
    """
    debut_saison = date(annee, 9, 1)
    fin_saison   = date(annee + 1, 6, 30)
    dates = []
    # Sep–Déc de l'année annee
    for d in _calculer_dates_regle(regle, annee):
        if d >= debut_saison:
            dates.append(d)
    # Jan–Jun de l'année annee+1
    for d in _calculer_dates_regle(regle, annee + 1):
        if d <= fin_saison:
            dates.append(d)
    # Filtre dates_debut/fin de la règle
    return [
        d for d in dates
        if not (regle.date_fin and d > regle.date_fin)
        and not (regle.date_debut and d < regle.date_debut)
    ]


def _dry_run_saison(annee):
    """
    Simule la génération d'une saison sans aucune écriture en base.
    Couvre 01/09/annee → 30/06/annee+1.
    Retourne une liste de dicts triée par date :
      statut  'ok'          → sera créée (nouvelle)
              'existe_deja' → réservation auto déjà présente, sera remplacée
              'conflit'     → conflit avec une réservation manuelle, sera ignorée
    """
    regles = RegleRecurrence.objects.filter(actif=True).select_related('loge', 'temple')
    lignes = []
    for regle in regles:
        for d in _dates_saison(regle, annee):
            cle = f"{regle.pk}:{d.isoformat()}"

            # Conflit avec réservation NON-auto sur le même créneau ?
            conflit_qs = Reservation.objects.filter(
                temple=regle.temple,
                date=d,
                statut__in=['validee', 'attente'],
                heure_debut__lt=regle.heure_fin,
                heure_fin__gt=regle.heure_debut,
            ).exclude(regle_source=regle).select_related('loge')

            if conflit_qs.exists():
                c = conflit_qs.first()
                statut = 'conflit'
                conflict_detail = (
                    f"{c.loge.nom if c.loge else c.nom_demandeur} "
                    f"({c.get_statut_display()}, "
                    f"{c.heure_debut:%H:%M}–{c.heure_fin:%H:%M})"
                )
            elif Reservation.objects.filter(regle_source=regle, date=d).exists():
                statut = 'existe_deja'
                conflict_detail = ''
            else:
                statut = 'ok'
                conflict_detail = ''

            lignes.append({
                'regle_id':       regle.pk,
                'regle_label':    str(regle),
                'loge':           regle.loge,
                'temple':         regle.temple,
                'date':           d,
                'jour':           _JOURS_FR[d.weekday()],
                'heure_debut':    regle.heure_debut,
                'heure_fin':      regle.heure_fin,
                'statut':         statut,
                'conflict_detail': conflict_detail,
                'cle':            cle,
            })

    lignes.sort(key=lambda x: x['date'])
    return lignes


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

        elif action == 'previsualiser_saison':
            annee_cible = int(request.POST.get('annee_cible'))
            lignes_preview = _dry_run_saison(annee_cible)
            nb_ok      = sum(1 for l in lignes_preview if l['statut'] == 'ok')
            nb_existe  = sum(1 for l in lignes_preview if l['statut'] == 'existe_deja')
            nb_conflit = sum(1 for l in lignes_preview if l['statut'] == 'conflit')
            return render(request, 'administration/gestion_saison.html', {
                'saisons':         saisons,
                'current_year':    current_year,
                'annees':          list(range(current_year - 1, current_year + 4)),
                'db_last_modified': _get_db_last_modified(),
                'preview_lignes':  lignes_preview,
                'preview_annee':   annee_cible,
                'preview_nb_ok':   nb_ok,
                'preview_nb_existe': nb_existe,
                'preview_nb_conflit': nb_conflit,
            })

        elif action == 'generer_saison_confirme':
            annee_cible   = int(request.POST.get('annee_cible'))
            selectionnees = set(request.POST.getlist('lignes_selectionnees'))
            appliquer_retours = request.POST.get('appliquer_retours') == '1'
            regles = RegleRecurrence.objects.filter(actif=True).select_related('loge', 'temple')
            cree = conflit = ignore = ignore_retour = 0

            # Pré-charger les lignes de validation marquées 'annuler' pour cette saison
            # Clé : (regle_id, date_iso) → True si la loge a demandé l'annulation
            annulations_loge: set = set()
            if appliquer_retours:
                for ligne in ValidationSaisonLigne.objects.filter(
                    validation__annee=annee_cible,
                    validation__statut__in=['soumise', 'traitee'],
                    avis='annuler',
                ).select_related('regle'):
                    if ligne.regle_id:
                        annulations_loge.add((ligne.regle_id, ligne.date.isoformat()))

            for regle in regles:
                for d in _dates_saison(regle, annee_cible):
                    cle = f"{regle.pk}:{d.isoformat()}"
                    if cle not in selectionnees:
                        ignore += 1
                        continue

                    # Retour loge : annulation demandée → on skip
                    if appliquer_retours and (regle.pk, d.isoformat()) in annulations_loge:
                        ignore_retour += 1
                        continue

                    Reservation.objects.filter(regle_source=regle, date=d).delete()

                    if Reservation.objects.filter(
                        temple=regle.temple, date=d, statut__in=['validee', 'attente'],
                        heure_debut__lt=regle.heure_fin, heure_fin__gt=regle.heure_debut,
                    ).exclude(regle_source=regle).exists():
                        conflit += 1
                        continue

                    Reservation.objects.create(
                        loge=regle.loge, temple=regle.temple, date=d,
                        heure_debut=regle.heure_debut, heure_fin=regle.heure_fin,
                        type_reservation='reguliere', statut='validee',
                        nom_demandeur='Generation automatique',
                        email_demandeur=regle.loge.email or settings.DEFAULT_FROM_EMAIL,
                        regle_source=regle,
                    )
                    cree += 1

            parts = [f"{cree} tenue(s) créée(s)"]
            if ignore:
                parts.append(f"{ignore} ignorée(s) (décochées)")
            if ignore_retour:
                parts.append(f"{ignore_retour} annulée(s) sur demande loge")
            if conflit:
                parts.append(f"{conflit} conflit(s) détecté(s)")
            messages.success(request, f"Saison {annee_cible} : {', '.join(parts)}.")
            return redirect('administration:gestion_saison')

    return render(request, 'administration/gestion_saison.html', {
        'saisons':         saisons,
        'current_year':    current_year,
        'annees':          list(range(current_year - 1, current_year + 4)),
        'db_last_modified': _get_db_last_modified(),
    })


@login_required
def preview_saison_excel(request):
    """Export Excel du dry-run groupé par loge."""
    from collections import defaultdict
    annee  = int(request.GET.get('annee', date.today().year))
    lignes = _dry_run_saison(annee)

    saison_label  = f"{annee}-{annee + 1}"
    periode_label = f"01/09/{annee} → 30/06/{annee + 1}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Saison {saison_label}"

    # ── Styles ──────────────────────────────────────────────────────────────────
    navy_fill  = PatternFill("solid", fgColor="0F2137")
    loge_fill  = PatternFill("solid", fgColor="1E3A5F")
    col_fill   = PatternFill("solid", fgColor="E2E8F0")
    total_fill = PatternFill("solid", fgColor="F1F5F9")
    grand_fill = PatternFill("solid", fgColor="0F2137")
    fill_ok      = PatternFill("solid", fgColor="D1FAE5")
    fill_existe  = PatternFill("solid", fgColor="FEF9C3")
    fill_conflit = PatternFill("solid", fgColor="FEE2E2")

    thin  = Border(left=Side(style='thin'), right=Side(style='thin'),
                   top=Side(style='thin'),  bottom=Side(style='thin'))
    ctr   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left  = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    NCOLS = 7  # Date | Jour | Temple | Horaires | Règle | Statut | Détail
    col_widths = [13, 10, 22, 13, 34, 22, 36]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    def _cell(r, c, val='', font=None, fill=None, align=None, border=thin):
        cell = ws.cell(row=r, column=c, value=val)
        if font:   cell.font      = font
        if fill:   cell.fill      = fill
        if align:  cell.alignment = align
        if border: cell.border    = border
        return cell

    def _merge_row(r, val, font, fill, height=18):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
        _cell(r, 1, val, font=font, fill=fill, align=ctr)
        for c in range(2, NCOLS + 1):
            ws.cell(row=r, column=c).fill  = fill
            ws.cell(row=r, column=c).border = thin
        ws.row_dimensions[r].height = height

    # ── En-tête document ────────────────────────────────────────────────────────
    row = 1
    _merge_row(row, "TEMPLES KELLERMANN",
               Font(bold=True, size=14, color="C8A84B"), navy_fill, height=26)
    row += 1
    _merge_row(row, f"Prévisualisation saison {saison_label}  ·  {periode_label}",
               Font(bold=True, size=11, color="FFFFFF"), navy_fill, height=20)
    row += 1

    nb_ok      = sum(1 for l in lignes if l['statut'] == 'ok')
    nb_existe  = sum(1 for l in lignes if l['statut'] == 'existe_deja')
    nb_conflit = sum(1 for l in lignes if l['statut'] == 'conflit')
    _merge_row(row, f"✓ {nb_ok} à créer   ·   ↻ {nb_existe} remplace existantes   ·   ⚠ {nb_conflit} conflits ignorés",
               Font(size=9, color="0F2137"), PatternFill("solid", fgColor="F0F9FF"), height=16)
    row += 2  # ligne vide

    # ── Regroupement par loge ───────────────────────────────────────────────────
    groupes: dict = defaultdict(list)
    for l in lignes:
        groupes[l['loge'].nom if l['loge'] else '— Sans loge —'].append(l)
    groupes_tries = sorted(groupes.items(), key=lambda x: x[0])

    COL_HEADERS = ["Date", "Jour", "Temple", "Horaires", "Règle de récurrence", "Statut", "Détail conflit"]
    STATUT_LABELS = {'ok': '✓ À créer', 'existe_deja': '↻ Remplace', 'conflit': '⚠ Conflit'}

    for loge_nom, loge_lignes in groupes_tries:
        nb_loge = len(loge_lignes)

        # En-tête loge
        _merge_row(row, f"  {loge_nom.upper()}  —  {nb_loge} tenue{'s' if nb_loge > 1 else ''}",
                   Font(bold=True, size=10, color="FFFFFF"), loge_fill, height=18)
        row += 1

        # En-têtes colonnes
        for c, h in enumerate(COL_HEADERS, 1):
            _cell(row, c, h,
                  font=Font(bold=True, size=9, color="0F2137"),
                  fill=col_fill, align=ctr)
        ws.row_dimensions[row].height = 15
        row += 1

        # Lignes de données
        loge_lignes_sorted = sorted(loge_lignes, key=lambda x: x['date'])
        for l in loge_lignes_sorted:
            fill = {'ok': fill_ok, 'existe_deja': fill_existe, 'conflit': fill_conflit}[l['statut']]
            font_data = Font(size=9, color="991B1B" if l['statut'] == 'conflit' else "000000")
            vals = [
                l['date'].strftime('%d/%m/%Y'),
                l['jour'],
                str(l['temple']),
                f"{l['heure_debut']:%H:%M}–{l['heure_fin']:%H:%M}",
                l['regle_label'],
                STATUT_LABELS[l['statut']],
                l['conflict_detail'] or '',
            ]
            for c, v in enumerate(vals, 1):
                _cell(row, c, v, font=font_data, fill=fill,
                      align=ctr if c in (1, 2, 4, 6) else left)
            ws.row_dimensions[row].height = 14
            row += 1

        # Total loge
        nb_ok_l      = sum(1 for l in loge_lignes if l['statut'] == 'ok')
        nb_existe_l  = sum(1 for l in loge_lignes if l['statut'] == 'existe_deja')
        nb_conflit_l = sum(1 for l in loge_lignes if l['statut'] == 'conflit')
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        _cell(row, 1,
              f"Total {loge_nom} : {nb_loge} tenue(s)   "
              f"[✓ {nb_ok_l}  ↻ {nb_existe_l}  ⚠ {nb_conflit_l}]",
              font=Font(bold=True, size=9, color="0F2137"),
              fill=total_fill, align=left)
        for c in range(2, NCOLS + 1):
            ws.cell(row=row, column=c).fill   = total_fill
            ws.cell(row=row, column=c).border = thin
        ws.row_dimensions[row].height = 14
        row += 2  # saut entre loges

    # ── Grand total ─────────────────────────────────────────────────────────────
    _merge_row(row,
               f"TOTAL SAISON {saison_label}  :  {len(lignes)} tenues   "
               f"[✓ {nb_ok} à créer   ↻ {nb_existe} remplace   ⚠ {nb_conflit} conflits]",
               Font(bold=True, size=11, color="C8A84B"), grand_fill, height=22)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = (
        f'attachment; filename="kellermann_saison_{saison_label}.xlsx"')
    wb.save(response)
    return response


@login_required
def preview_saison_pdf(request):
    """Export PDF du dry-run groupé par loge."""
    from io import BytesIO
    from collections import defaultdict
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

    annee = int(request.GET.get('annee', date.today().year))
    lignes = _dry_run_saison(annee)

    saison_label  = f"{annee}-{annee + 1}"
    periode_label = f"01/09/{annee} \u2192 30/06/{annee + 1}"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    navy        = colors.HexColor('#0F2137')
    gold        = colors.HexColor('#C8A84B')
    loge_color  = colors.HexColor('#1E3A5F')
    col_bg      = colors.HexColor('#E2E8F0')
    total_bg    = colors.HexColor('#DBEAFE')
    fill_ok     = colors.HexColor('#D1FAE5')
    fill_existe = colors.HexColor('#FEF9C3')
    fill_conflit= colors.HexColor('#FEE2E2')
    green_dark  = colors.HexColor('#166534')
    yellow_dark = colors.HexColor('#92400E')
    red_dark    = colors.HexColor('#991B1B')
    grid_color  = colors.HexColor('#CBD5E1')

    nb_ok      = sum(1 for l in lignes if l['statut'] == 'ok')
    nb_existe  = sum(1 for l in lignes if l['statut'] == 'existe_deja')
    nb_conflit = sum(1 for l in lignes if l['statut'] == 'conflit')

    STATUT_LABELS = {'ok': '\u2713 \u00c0 cr\u00e9er', 'existe_deja': '\u21bb Remplace', 'conflit': '\u26a0 Conflit'}
    COL_HEADERS   = ["Date", "Jour", "Temple", "Horaires", "R\u00e8gle de r\u00e9currence", "Statut", "D\u00e9tail conflit"]

    # Columns: Date | Jour | Temple | Horaires | Règle | Statut | Conflit
    col_widths = [2.2*cm, 1.5*cm, 6.2*cm, 2.4*cm, 7.2*cm, 2.5*cm, 4.2*cm]
    NCOLS      = len(col_widths)
    total_w    = sum(col_widths)

    story = []

    # ── En-tête document ────────────────────────────────────────────────────────
    header_data = [
        ["TEMPLES KELLERMANN"],
        [f"Pr\u00e9visualisation saison {saison_label}  \u00b7  {periode_label}"],
        [f"\u2713 {nb_ok} \u00e0 cr\u00e9er   \u00b7   \u21bb {nb_existe} remplace existantes   \u00b7   \u26a0 {nb_conflit} conflits ignor\u00e9s"],
    ]
    header_table = Table(header_data, colWidths=[total_w])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), navy),
        ('TEXTCOLOR',    (0,0), (-1,0), gold),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,0), 16),
        ('BACKGROUND',   (0,1), (-1,1), navy),
        ('TEXTCOLOR',    (0,1), (-1,1), colors.white),
        ('FONTNAME',     (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,1), (-1,1), 11),
        ('BACKGROUND',   (0,2), (-1,2), colors.HexColor('#EFF6FF')),
        ('TEXTCOLOR',    (0,2), (-1,2), navy),
        ('FONTSIZE',     (0,2), (-1,2), 9),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',   (0,0), (-1,0), 6),
        ('BOTTOMPADDING',(0,0), (-1,0), 6),
        ('TOPPADDING',   (0,1), (-1,1), 4),
        ('BOTTOMPADDING',(0,1), (-1,1), 4),
        ('TOPPADDING',   (0,2), (-1,2), 3),
        ('BOTTOMPADDING',(0,2), (-1,2), 3),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*cm))

    # ── Regroupement par loge ───────────────────────────────────────────────────
    groupes: dict = defaultdict(list)
    for l in lignes:
        groupes[l['loge'].nom if l['loge'] else '\u2014 Sans loge \u2014'].append(l)
    groupes_tries = sorted(groupes.items(), key=lambda x: x[0])

    for loge_nom, loge_lignes in groupes_tries:
        nb_loge      = len(loge_lignes)
        nb_ok_l      = sum(1 for l in loge_lignes if l['statut'] == 'ok')
        nb_existe_l  = sum(1 for l in loge_lignes if l['statut'] == 'existe_deja')
        nb_conflit_l = sum(1 for l in loge_lignes if l['statut'] == 'conflit')

        loge_lignes_sorted = sorted(loge_lignes, key=lambda x: x['date'])
        data       = []
        style_cmds = []

        # Ligne 0 — en-tête loge
        data.append([f"  {loge_nom.upper()}  \u2014  {nb_loge} tenue{'s' if nb_loge > 1 else ''}"] + [''] * (NCOLS - 1))
        style_cmds += [
            ('SPAN',         (0,0), (NCOLS-1, 0)),
            ('BACKGROUND',   (0,0), (-1,0), loge_color),
            ('TEXTCOLOR',    (0,0), (-1,0), colors.white),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,0), 10),
            ('ALIGN',        (0,0), (-1,0), 'LEFT'),
            ('VALIGN',       (0,0), (-1,0), 'MIDDLE'),
            ('TOPPADDING',   (0,0), (-1,0), 5),
            ('BOTTOMPADDING',(0,0), (-1,0), 5),
        ]

        # Ligne 1 — en-têtes colonnes
        data.append(COL_HEADERS)
        style_cmds += [
            ('BACKGROUND',   (0,1), (-1,1), col_bg),
            ('TEXTCOLOR',    (0,1), (-1,1), navy),
            ('FONTNAME',     (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,1), (-1,1), 8),
            ('ALIGN',        (0,1), (-1,1), 'CENTER'),
            ('VALIGN',       (0,1), (-1,1), 'MIDDLE'),
            ('TOPPADDING',   (0,1), (-1,1), 3),
            ('BOTTOMPADDING',(0,1), (-1,1), 3),
        ]

        # Lignes de données
        for i, l in enumerate(loge_lignes_sorted):
            ri = 2 + i
            data.append([
                l['date'].strftime('%d/%m/%Y'),
                l['jour'][:3],
                str(l['temple']),
                f"{l['heure_debut']:%H:%M}\u2013{l['heure_fin']:%H:%M}",
                l['regle_label'],
                STATUT_LABELS[l['statut']],
                l['conflict_detail'] or '',
            ])
            if l['statut'] == 'ok':
                style_cmds.append(('BACKGROUND', (0,ri), (-1,ri), fill_ok))
                style_cmds.append(('TEXTCOLOR',  (5,ri), (5,ri),  green_dark))
            elif l['statut'] == 'existe_deja':
                style_cmds.append(('BACKGROUND', (0,ri), (-1,ri), fill_existe))
                style_cmds.append(('TEXTCOLOR',  (5,ri), (5,ri),  yellow_dark))
            else:
                style_cmds.append(('BACKGROUND', (0,ri), (-1,ri), fill_conflit))
                style_cmds.append(('TEXTCOLOR',  (0,ri), (-1,ri), red_dark))
                style_cmds.append(('FONTNAME',   (0,ri), (-1,ri), 'Helvetica-Bold'))

        # Ligne total loge
        ti = len(data)
        data.append(
            [f"Total {loge_nom} : {nb_loge} tenue(s)   "
             f"[\u2713 {nb_ok_l}  \u21bb {nb_existe_l}  \u26a0 {nb_conflit_l}]"]
            + [''] * (NCOLS - 1)
        )
        style_cmds += [
            ('SPAN',         (0,ti), (NCOLS-1, ti)),
            ('BACKGROUND',   (0,ti), (-1,ti), total_bg),
            ('TEXTCOLOR',    (0,ti), (-1,ti), navy),
            ('FONTNAME',     (0,ti), (-1,ti), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,ti), (-1,ti), 8),
            ('ALIGN',        (0,ti), (-1,ti), 'LEFT'),
            ('TOPPADDING',   (0,ti), (-1,ti), 4),
            ('BOTTOMPADDING',(0,ti), (-1,ti), 4),
        ]

        # Style global données
        style_cmds += [
            ('FONTSIZE',     (0,2), (-1,ti-1), 7.5),
            ('VALIGN',       (0,2), (-1,ti-1), 'MIDDLE'),
            ('ALIGN',        (0,2), (-1,ti-1), 'LEFT'),
            ('ALIGN',        (0,2), (0,ti-1),  'CENTER'),
            ('ALIGN',        (1,2), (1,ti-1),  'CENTER'),
            ('ALIGN',        (3,2), (3,ti-1),  'CENTER'),
            ('ALIGN',        (5,2), (5,ti-1),  'CENTER'),
            ('TOPPADDING',   (0,2), (-1,ti-1), 2),
            ('BOTTOMPADDING',(0,2), (-1,ti-1), 2),
            ('GRID',         (0,1), (-1,-1), 0.3, grid_color),
        ]

        loge_table = Table(data, colWidths=col_widths, repeatRows=2)
        loge_table.setStyle(TableStyle(style_cmds))
        story.append(loge_table)
        story.append(Spacer(1, 0.2*cm))

    # ── Grand total ─────────────────────────────────────────────────────────────
    grand_data = [
        [f"TOTAL SAISON {saison_label}  :  {len(lignes)} tenues   "
         f"[\u2713 {nb_ok} \u00e0 cr\u00e9er   \u21bb {nb_existe} remplace   \u26a0 {nb_conflit} conflits]"]
        + [''] * (NCOLS - 1)
    ]
    grand_table = Table(grand_data, colWidths=col_widths)
    grand_table.setStyle(TableStyle([
        ('SPAN',         (0,0), (NCOLS-1, 0)),
        ('BACKGROUND',   (0,0), (-1,0), navy),
        ('TEXTCOLOR',    (0,0), (-1,0), gold),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,0), 11),
        ('ALIGN',        (0,0), (-1,0), 'CENTER'),
        ('VALIGN',       (0,0), (-1,0), 'MIDDLE'),
        ('TOPPADDING',   (0,0), (-1,0), 8),
        ('BOTTOMPADDING',(0,0), (-1,0), 8),
    ]))
    story.append(grand_table)

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="kellermann_saison_{saison_label}.pdf"')
    return response


@login_required
def validation_saison_admin(request):
    """Dashboard de validation de saison par les loges."""
    from django.utils import timezone

    current_year = date.today().year
    annees = list(range(current_year - 1, current_year + 4))
    annee = int(request.GET.get('annee', current_year))
    saison_label  = f"{annee}-{annee + 1}"
    periode_label = f"01/09/{annee} → 30/06/{annee + 1}"

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ouvrir_validation':
            # ── ÉTAPE 1 : calcul + création des fiches, AUCUN email ──────────
            annee_cible = int(request.POST.get('annee_cible', annee))
            lignes_dry  = _dry_run_saison(annee_cible)

            from collections import defaultdict
            lignes_par_loge = defaultdict(list)
            for l in lignes_dry:
                if l['statut'] in ('ok', 'existe_deja') and l['loge']:
                    lignes_par_loge[l['loge']].append(l)

            nb_cree = nb_maj = nb_skip_soumise = 0
            for loge, loge_lignes in lignes_par_loge.items():
                val, created = ValidationSaison.objects.get_or_create(
                    loge=loge, annee=annee_cible,
                    defaults={'statut': 'attente'},
                )
                if not created and val.statut == 'soumise':
                    nb_skip_soumise += 1
                    continue

                # (Re)créer les lignes sans toucher au statut ni aux emails
                val.lignes.all().delete()
                ValidationSaisonLigne.objects.bulk_create([
                    ValidationSaisonLigne(
                        validation=val,
                        regle_id=l['regle_id'],
                        date=l['date'],
                        heure_debut=l['heure_debut'],
                        heure_fin=l['heure_fin'],
                        temple_nom=str(l['temple']),
                    )
                    for l in sorted(loge_lignes, key=lambda x: x['date'])
                ])

                # Statut attente uniquement si nouveau ou remis à zéro
                if created or val.statut not in ('ouverte', 'traitee'):
                    val.statut = 'attente'
                val.save()
                if created:
                    nb_cree += 1
                else:
                    nb_maj += 1

            parts = [f"{len(lignes_par_loge)} fiche(s) calculée(s)"]
            if nb_cree:
                parts.append(f"{nb_cree} nouvelle(s)")
            if nb_maj:
                parts.append(f"{nb_maj} mise(s) à jour")
            if nb_skip_soumise:
                parts.append(f"{nb_skip_soumise} déjà soumise(s) — non modifiée(s)")
            messages.info(request,
                "Récapitulatif calculé — aucun email envoyé. "
                "Vérifiez le tableau ci-dessous puis cliquez sur «\u00a0Envoyer les emails\u00a0». "
                f"({', '.join(parts)})")
            log_evenement('ouverture_validation_saison',
                f"Ouverture validation saison {annee_cible}-{annee_cible + 1} : {', '.join(parts)}",
                request=request, objet_type='systeme')
            return redirect(f"{request.path}?annee={annee_cible}")

        elif action == 'envoyer_emails':
            # ── ÉTAPE 2 : envoi des emails aux loges sélectionnées ───────────
            annee_cible  = int(request.POST.get('annee_cible', annee))
            periode_cible = f"01/09/{annee_cible} → 30/06/{annee_cible + 1}"
            pks_selectionnes = set(
                int(x) for x in request.POST.getlist('validation_pks') if x.isdigit()
            )
            if not pks_selectionnes:
                messages.warning(request, "Aucune loge sélectionnée.")
                return redirect(f"{request.path}?annee={annee_cible}")
            validations_attente = ValidationSaison.objects.filter(
                pk__in=pks_selectionnes, annee=annee_cible, statut='attente'
            ).select_related('loge')

            nb_email = nb_sans_email = nb_sans_token = 0
            for val in validations_attente:
                loge = val.loge
                nb_tenues = val.lignes.count()

                if loge.email:
                    demande = DemandeAccesPortail.objects.filter(
                        loge=loge, statut='validee'
                    ).order_by('-created_at').first()
                    if demande:
                        portail_url = (
                            f"{settings.SITE_URL.rstrip('/')}"
                            f"/reservations/portail/{demande.token}/"
                        ) if hasattr(settings, 'SITE_URL') else f"/reservations/portail/{demande.token}/"
                        send_mail_kellermann(
                            subject=f"Validation de votre calendrier — Saison {annee_cible}-{annee_cible + 1}",
                            message=(
                                f"Bonjour,\n\n"
                                f"Nous vous invitons à valider le calendrier prévisionnel de vos tenues "
                                f"pour la saison {annee_cible}-{annee_cible + 1} ({periode_cible}).\n\n"
                                f"{nb_tenues} tenue(s) sont planifiées pour votre loge.\n\n"
                                f"Accédez à votre espace loge pour confirmer, signaler un déplacement "
                                f"ou une annulation :\n{portail_url}\n\n"
                                f"Bien fraternellement,\nLes Temples Kellermann"
                            ),
                            recipient_list=[loge.email],
                        )
                        val.statut     = 'ouverte'
                        val.date_envoi = timezone.now()
                        nb_email += 1
                    else:
                        # Email présent mais pas de token portail
                        val.statut = 'ouverte'
                        nb_sans_token += 1
                else:
                    val.statut = 'ouverte'
                    nb_sans_email += 1

                val.save()

            parts = [f"{nb_email} email(s) envoyé(s)"]
            if nb_sans_token:
                parts.append(f"{nb_sans_token} sans token portail")
            if nb_sans_email:
                parts.append(f"{nb_sans_email} sans adresse email")
            messages.success(request, "Emails envoyés — " + ", ".join(parts) + ".")
            log_evenement('envoi_emails_saison',
                f"Envoi emails validation saison {annee_cible}-{annee_cible + 1} : {', '.join(parts)}",
                request=request, objet_type='systeme')
            return redirect(f"{request.path}?annee={annee_cible}")

        elif action == 'marquer_traitee':
            pk = int(request.POST.get('validation_pk'))
            val = ValidationSaison.objects.get(pk=pk)
            val.statut = 'traitee'
            val.save()
            messages.success(request, f"{val.loge} — saison {val.annee}-{val.annee + 1} marquée comme traitée.")
            return redirect(f"{request.path}?annee={annee}")

        elif action == 'reinitialiser':
            pk = int(request.POST.get('validation_pk'))
            val = ValidationSaison.objects.get(pk=pk)
            val.statut = 'ouverte'
            val.commentaire_loge = ''
            val.date_reponse = None
            val.lignes.update(avis='ok', commentaire='')
            val.save()
            messages.success(request, f"Validation de {val.loge} réinitialisée.")
            return redirect(f"{request.path}?annee={annee}")

    # ── GET ──────────────────────────────────────────────────────────────────────
    validations = (
        ValidationSaison.objects
        .filter(annee=annee)
        .select_related('loge')
        .prefetch_related('lignes')
        .order_by('loge__nom')
    )

    # Statistiques globales
    nb_total   = validations.count()
    nb_attente = validations.filter(statut='attente').count()
    nb_ouverte = validations.filter(statut='ouverte').count()
    nb_soumise = validations.filter(statut='soumise').count()
    nb_traitee = validations.filter(statut='traitee').count()
    nb_anomalies_total = sum(v.nb_anomalies() for v in validations)

    # Loges avec au moins une tenue projetée pour cette année
    # mais sans fiche ValidationSaison — on réutilise le dry-run
    # uniquement si des fiches existent déjà (évite le calcul à froid)
    loges_validees = set(validations.values_list('loge_id', flat=True))
    if validations.exists():
        lignes_dry = _dry_run_saison(annee)
        loges_avec_tenues = {
            l['loge'].pk
            for l in lignes_dry
            if l['statut'] in ('ok', 'existe_deja') and l['loge']
        }
        loges_manquantes = Loge.objects.filter(
            pk__in=loges_avec_tenues - loges_validees
        ).order_by('nom')
    else:
        loges_manquantes = Loge.objects.none()

    validations_attente_list = [v for v in validations if v.statut == 'attente']

    return render(request, 'administration/validation_saison.html', {
        'annee':                   annee,
        'annees':                  annees,
        'saison_label':            saison_label,
        'periode_label':           periode_label,
        'validations':             validations,
        'validations_attente_list': validations_attente_list,
        'nb_total':                nb_total,
        'nb_attente':              nb_attente,
        'nb_ouverte':              nb_ouverte,
        'nb_soumise':              nb_soumise,
        'nb_traitee':              nb_traitee,
        'nb_anomalies_total':      nb_anomalies_total,
        'loges_manquantes':        loges_manquantes,
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
    log_evenement('backup_base',
        f"Téléchargement backup base de données : {filename}",
        request=request, objet_type='systeme')
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
        params.email_admin    = request.POST.get('email_admin',    params.email_admin)
        params.email_traiteur = request.POST.get('email_traiteur', params.email_traiteur)
        params.email_from     = request.POST.get('email_from',     params.email_from)
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


def _couverts_admin(t):
    """(valeur_int, est_estimation)
    est_estimation=True + valeur=0  →  non renseigné (afficher '~?')
    est_estimation=True + valeur>0  →  estimation via effectif_moyen_agapes
    est_estimation=False            →  valeur confirmée
    """
    nombre = getattr(t, 'nombre_repas', 0) or 0
    if nombre > 0:
        return (nombre, False)
    loge = getattr(t, 'loge', None)
    if loge is not None:
        effectif = getattr(loge, 'effectif_moyen_agapes', 0) or 0
        if effectif > 0:
            return (effectif, True)
    # Aucune donnée disponible — signalé comme estimation inconnue
    return (0, True)


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
        couverts, est_estim = _couverts_admin(t)
        lignes.append({
            'date':           t.date,
            'organisation':   t.loge.nom if t.loge else (t.nom_organisation or t.nom_demandeur),
            'type':           'Tenue + agapes',
            'couverts':       couverts,
            'est_estimation': est_estim,
            'lieu':           str(t.temple),
            'horaires':       f"{t.heure_debut:%H:%M} – {t.heure_fin:%H:%M}",
            'commentaire':    t.commentaire,
        })
    for b in banquets:
        lignes.append({
            'date':           b.date,
            'organisation':   b.organisation or b.nom_demandeur,
            'type':           "Banquet d'ordre",
            'couverts':       b.nombre_participants,
            'est_estimation': False,
            'lieu':           str(b.salle),
            'horaires':       f"{b.heure_debut:%H:%M} – {b.heure_fin:%H:%M}",
            'commentaire':    b.commentaire,
        })
    lignes.sort(key=lambda x: x['date'])

    # Totaux par mois — tous les mois de la saison, même vides
    MOIS_ORDRE = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
    MOIS_NOMS  = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                  9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}
    totaux_mois = {}
    for m in MOIS_ORDRE:
        sous_liste = [l for l in lignes if l['date'].month == m]
        totaux_mois[m] = {
            'nom':            MOIS_NOMS[m],
            'lignes':         sous_liste,
            'total':          sum(l['couverts'] for l in sous_liste),
            'has_estimations': any(l['est_estimation'] for l in sous_liste),
        }

    context = {
        'lignes':        lignes,
        'totaux_mois':   totaux_mois,
        'total_saison':  sum(l['couverts'] for l in lignes),
        'has_estimations': any(l['est_estimation'] for l in lignes),
        'annee':         annee_param,
        'annees':        list(range(annee_courante - 2, annee_courante + 4)),
        'saison_label':  f"{annee_param}/{annee_param + 1}",
        'mois_liste':    [(m, MOIS_NOMS[m]) for m in MOIS_ORDRE],
    }
    return render(request, 'administration/agapes_traiteur.html', context)


@login_required
def agapes_export_excel(request):
    """Export Excel agapes/banquets — période et type filtrables."""
    from datetime import datetime as dt
    today = date.today()
    annee_courante = today.year if today.month >= 9 else today.year - 1

    # Paramètres de filtrage
    annee_param  = int(request.GET.get('annee', annee_courante))
    date_debut_s = request.GET.get('date_debut', '')
    date_fin_s   = request.GET.get('date_fin', '')
    type_export  = request.GET.get('type_export', 'tout')  # tout | agapes | banquet

    try:
        debut_saison = dt.strptime(date_debut_s, '%Y-%m-%d').date() if date_debut_s else date(annee_param, 9, 1)
        fin_saison   = dt.strptime(date_fin_s,   '%Y-%m-%d').date() if date_fin_s   else date(annee_param + 1, 6, 30)
    except ValueError:
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
    if type_export == 'agapes':
        banquets = banquets.none()
    elif type_export == 'banquet':
        tenues = tenues.none()

    lignes = []
    for t in tenues:
        couverts, est_estim = _couverts_admin(t)
        couverts_affiche = f"~{couverts} (estim.)" if est_estim else couverts
        lignes.append((
            t.date,
            t.loge.nom if t.loge else (t.nom_organisation or t.nom_demandeur),
            'Tenue + agapes',
            couverts_affiche,
            couverts,
            str(t.temple),
            f"{t.heure_debut:%H:%M} – {t.heure_fin:%H:%M}",
            t.commentaire,
        ))
    for b in banquets:
        lignes.append((
            b.date,
            b.organisation or b.nom_demandeur,
            "Banquet d'ordre",
            b.nombre_participants,
            b.nombre_participants,
            str(b.salle),
            f"{b.heure_debut:%H:%M} – {b.heure_fin:%H:%M}",
            b.commentaire,
        ))
    lignes.sort(key=lambda x: x[0])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Agapes {debut_saison:%d/%m/%Y}-{fin_saison:%d/%m/%Y}"[:31]

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
                 7:'Juillet',8:'Août',9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}

    # Construire l'ordre des mois couverts par la période réelle
    mois_presents = sorted({l[0].month for l in lignes}, key=lambda m: (m < debut_saison.month, m))
    # Fallback saison classique si aucune donnée
    if not mois_presents:
        mois_presents = []

    # Tuple layout : (date_obj, organisation, type, couverts_affiche, couverts_num, lieu, horaires, commentaire)
    row_idx = 2
    for mois in mois_presents:
        mois_lignes = sorted([l for l in lignes if l[0].month == mois], key=lambda l: l[0])
        if not mois_lignes:
            continue
        # Séparateur de mois
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=7)
        sep = ws.cell(row=row_idx, column=1, value=MOIS_NOMS[mois].upper())
        sep.font = Font(bold=True, color="0F2137")
        sep.fill = PatternFill("solid", fgColor="E2E8F0")
        sep.alignment = ctr; sep.border = thin
        row_idx += 1
        # Lignes — 7 colonnes Excel : date, org, type, couverts, lieu, horaires, commentaire
        for l in mois_lignes:
            excel_row = [l[0].strftime('%d/%m/%Y'), l[1], l[2], l[3], l[5], l[6], l[7]]
            for col, val in enumerate(excel_row, 1):
                c = ws.cell(row=row_idx, column=col, value=val)
                c.border = thin
                if col == 4:  # Couverts
                    c.alignment = ctr
            row_idx += 1
        # Total mois (valeur numérique = index 4)
        total = sum(l[4] for l in mois_lignes)
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
    total_saison = sum(l[4] for l in lignes)
    row_idx += 1
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=3)
    ws.cell(row=row_idx, column=1, value=f"TOTAL  {debut_saison:%d/%m/%Y} → {fin_saison:%d/%m/%Y}").font = Font(bold=True, color="C8A84B")
    ws.cell(row=row_idx, column=1).fill = PatternFill("solid", fgColor="0F2137")
    ws.cell(row=row_idx, column=1).border = thin
    ts = ws.cell(row=row_idx, column=4, value=total_saison)
    ts.font = Font(bold=True, color="C8A84B")
    ts.fill = PatternFill("solid", fgColor="0F2137")
    ts.alignment = ctr; ts.border = thin

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    periode_label = f"{debut_saison:%d%m%Y}-{fin_saison:%d%m%Y}"
    response['Content-Disposition'] = f'attachment; filename="agapes_{periode_label}.xlsx"'
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


# ── Réservation directe (admin) ───────────────────────────────────────────────

@login_required
def reservation_directe(request):
    """Créer une réservation directement validée (sans workflow de validation)."""
    from temple_project.apps.traiteur.forms import ReservationDirecteForm

    form = ReservationDirecteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cd        = form.cleaned_data
        type_resa = cd["type_resa"]
        loge      = cd.get("loge")
        org       = cd.get("organisation") or ""
        nom_dem   = cd["nom_demandeur"]
        email_dem = cd["email_demandeur"]
        date_r    = cd["date"]
        hd        = cd["heure_debut"]
        hf        = cd["heure_fin"]
        couverts  = cd.get("nombre_repas") or 0
        note      = cd.get("note") or ""

        if type_resa == "temple":
            temple = cd["temple"]
            resa = Reservation.objects.create(
                loge=loge,
                nom_organisation=org,
                temple=temple,
                type_reservation="exceptionnelle",
                sous_type="standard",
                statut="validee",
                date=date_r,
                heure_debut=hd,
                heure_fin=hf,
                besoin_agapes=couverts > 0,
                nombre_repas=couverts,
                nom_demandeur=nom_dem,
                email_demandeur=email_dem,
                commentaire=note,
            )
            messages.success(request, "Réservation temple créée et validée.")
            log_evenement('creation_reservation_directe',
                f"Réservation directe temple : {loge or org} — {date_r:%d/%m/%Y} {hd:%H:%M}–{hf:%H:%M} ({temple})",
                request=request, objet=resa)
        else:
            salle = cd["salle"]
            resa_salle = ReservationSalle.objects.create(
                loge=loge,
                salle=salle,
                date=date_r,
                heure_debut=hd,
                heure_fin=hf,
                statut="validee",
                nom_demandeur=nom_dem,
                email_demandeur=email_dem,
                organisation=loge.nom if loge else org,
                objet="Agapes" if not note else note,
                nombre_participants=couverts,
                commentaire=note,
            )
            messages.success(request, "Réservation salle créée et validée.")
            log_evenement('creation_reservation_directe',
                f"Réservation directe salle : {loge.nom if loge else org} — {date_r:%d/%m/%Y} {hd:%H:%M}–{hf:%H:%M} ({salle})",
                request=request, objet=resa_salle)

        return redirect("administration:tableau_de_bord")

    return render(request, "administration/reservation_directe.html", {"form": form})


# ── Journal de traçabilité ────────────────────────────────────────────────────

@login_required
def journal(request):
    """Journal de traçabilité — accès staff uniquement."""
    from django.contrib.auth import get_user_model
    from django.core.paginator import Paginator

    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé aux administrateurs.")

    User = get_user_model()

    qs = JournalEvenement.objects.select_related('utilisateur').order_by('-date_heure')

    # ── Filtres ───────────────────────────────────────────────────────────────
    f_type       = request.GET.get('type', '').strip()
    f_date_debut = request.GET.get('date_debut', '').strip()
    f_date_fin   = request.GET.get('date_fin', '').strip()
    f_loge       = request.GET.get('loge', '').strip()
    f_user       = request.GET.get('utilisateur', '').strip()

    if f_type:
        qs = qs.filter(type_evenement=f_type)
    if f_date_debut:
        try:
            from datetime import date as _date
            qs = qs.filter(date_heure__date__gte=_date.fromisoformat(f_date_debut))
        except ValueError:
            pass
    if f_date_fin:
        try:
            from datetime import date as _date
            qs = qs.filter(date_heure__date__lte=_date.fromisoformat(f_date_fin))
        except ValueError:
            pass
    if f_loge:
        qs = qs.filter(objet_type='loge', objet_id=f_loge)
    if f_user:
        qs = qs.filter(utilisateur_id=f_user)

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator   = Paginator(qs, 50)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    # GET params sans 'page' (pour les liens de pagination)
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    get_params = get_copy.urlencode()

    # Données pour les selects de filtres
    types_choices    = JournalEvenement.TYPE_CHOICES
    loges_list       = Loge.objects.order_by('nom')
    utilisateurs_list = User.objects.filter(
        evenements_journal__isnull=False
    ).distinct().order_by('username')

    return render(request, 'administration/journal.html', {
        'page_obj':          page_obj,
        'paginator':         paginator,
        'get_params':        get_params,
        'types_choices':     types_choices,
        'loges_list':        loges_list,
        'utilisateurs_list': utilisateurs_list,
        'f_type':            f_type,
        'f_date_debut':      f_date_debut,
        'f_date_fin':        f_date_fin,
        'f_loge':            f_loge,
        'f_user':            f_user,
        'total':             qs.count(),
    })
