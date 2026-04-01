from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
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

    # Détection conflits
    conflits = ReservationSalle.objects.filter(
        salle=resa.salle,
        date=resa.date,
        statut='validee',
        heure_debut__lt=resa.heure_fin,
        heure_fin__gt=resa.heure_debut,
    ).exclude(pk=pk)

    if request.method == 'POST':
        action            = request.POST.get('action')
        commentaire_admin = request.POST.get('commentaire_admin', '').strip()

        if action not in ('valider', 'refuser'):
            messages.error(request, "Action invalide.")
            return redirect('administration:tableau_de_bord')

        resa.statut = 'validee' if action == 'valider' else 'refusee'
        resa.save()

        _envoyer_email_decision_salle(resa, action, commentaire_admin)

        if action == 'valider':
            messages.success(request, f"Demande de salle pour {resa.organisation} validée — email envoyé à {resa.email_demandeur}.")
        else:
            messages.warning(request, f"Demande de salle pour {resa.organisation} refusée — email envoyé à {resa.email_demandeur}.")

        return redirect('administration:tableau_de_bord')

    return render(request, 'administration/valider_reservation_salle.html', {
        'reservation': resa,
        'conflits':    conflits,
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
        send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL, [resa.email_demandeur], fail_silently=False)
    except Exception as e:
        print(f"Erreur email decision : {e}")


def _envoyer_email_decision_salle(resa, action, commentaire_admin=''):
    validee = (action == 'valider')
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
        send_mail(sujet, corps, settings.DEFAULT_FROM_EMAIL, [resa.email_demandeur], fail_silently=False)
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
            data = {
                'loge_id': request.POST['loge'], 'temple_id': request.POST['temple'],
                'jour_semaine': int(request.POST['jour_semaine']),
                'numero_semaine': int(request.POST['numero_semaine']),
                'heure_debut': request.POST['heure_debut'], 'heure_fin': request.POST['heure_fin'],
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
            ('09:00','09h00'),('09:30','09h30'),('10:00','10h00'),
            ('14:00','14h00'),('14:30','14h30'),('19:00','19h00'),
            ('19:30','19h30'),('20:00','20h00'),('20:30','20h30'),
            ('21:00','21h00'),('22:00','22h00'),('22:30','22h30'),('23:00','23h00'),
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
            for d in _calculer_dates_regle(regle, annee):
                if d.month in [7, 8]:
                    continue
                if regle.date_fin and d > regle.date_fin:
                    continue
                if regle.date_debut and d < regle.date_debut:
                    continue
                if mode == 'remplacer':
                    Reservation.objects.filter(regle_source=regle, date=d).delete()
                if Reservation.objects.filter(temple=regle.temple, date=d, statut__in=['validee','attente'], heure_debut__lt=regle.heure_fin, heure_fin__gt=regle.heure_debut).exclude(regle_source=regle).exists():
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
            messages.success(request, f"{cree} tenues créées pour {annee}.")
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

@login_required
def telecharger_template_excel(request):
    wb = openpyxl.Workbook()
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor="0F2137")
    ctr = Alignment(horizontal="center", vertical="center")
    thin = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    ws = wb.active
    ws.title = "LOGES"
    for col, h in enumerate(["Abréviation","Nom complet","Obédience","Type","Email","Effectif total","Moy. agapes"], 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = hf; c.fill = hfill; c.alignment = ctr; c.border = thin
    for ri, row in enumerate([["3P","Les 3 Piliers","GODF","loge","contact@loge.fr",45,30],["14GO","4/14 Consistoire GODF","GODF","haut_grade","",20,0]], 2):
        for ci, v in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=v); c.border = thin; c.alignment = ctr
    for col, w in zip(['A','B','C','D','E','F','G'], [12,35,12,12,25,14,12]):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("REGLES RECURRENCE")
    for col, h in enumerate(["Abréviation","Nom complet","Obédience","Type","Temple","Jour","N° semaine","Heure début","Heure fin"], 1):
        c = ws2.cell(row=1, column=col, value=h)
        c.font = hf; c.fill = hfill; c.alignment = ctr; c.border = thin
    ws2.cell(row=3, column=1, value="Temples : Lafayette, Liberte, Egalite, Fraternite")
    ws2.cell(row=4, column=1, value="Jours : Lundi, Mardi, Mercredi, Jeudi, Vendredi, Samedi, Dimanche")
    ws2.cell(row=5, column=1, value="N° semaine : 1, 2, 3, 4 ou -1 (derniere)")
    for ci, v in enumerate(["3P","Les 3 Piliers","GODF","loge","Lafayette","Lundi",2,"19:30","22:30"], 1):
        c = ws2.cell(row=2, column=ci, value=v); c.border = thin; c.alignment = ctr
    ws2.column_dimensions['B'].width = 35

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Template_Kellermann_Import.xlsx"'
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
                RITES_VALIDES = ['reaa','rer','rf','rem','dh','mem','autre']
                rite = str(row[7]).strip().lower() if len(row) > 7 and row[7] else ''
                if rite not in RITES_VALIDES: rite = ''
                _, cl = Loge.objects.update_or_create(
                    abreviation=str(row[0]).strip(),
                    defaults={'nom': str(row[1]).strip() if row[1] else str(row[0]).strip(), 'obedience': ob,
                              'type_loge': str(row[3]).strip() if row[3] in ('loge','haut_grade') else 'loge',
                              'rite': rite,
                              'email': str(row[4]).strip() if row[4] else '',
                              'effectif_total': int(row[5]) if row[5] and str(row[5]).isdigit() else 0,
                              'effectif_moyen_agapes': int(row[6]) if row[6] and str(row[6]).isdigit() else 0}
                )
                if cl: stats['loges'] += 1
            except Exception as e:
                errors.append(f"LOGES ligne {i} : {e}")

    if 'REGLES RECURRENCE' in wb.sheetnames:
        JOURS  = {'Lundi':0,'Mardi':1,'Mercredi':2,'Jeudi':3,'Vendredi':4,'Samedi':5,'Dimanche':6}
        TEMPLES = {'Lafayette':'lafayette','Liberte':'liberte','Egalite':'egalite','Fraternite':'fraternite'}
        for i, row in enumerate(wb['REGLES RECURRENCE'].iter_rows(min_row=2, values_only=True), 2):
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
    return [d for mois in range(1, 13) for d in [_nieme_jour_du_mois(annee, mois, regle.numero_semaine, regle.jour_semaine)] if d]


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
        # Mettre à jour settings si nécessaire, mais pour simplifier, on surcharge dans views
        return redirect('administration:parametres')
    return render(request, 'administration/parametres.html', {'params': params})


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
