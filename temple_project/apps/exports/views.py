import csv
import io
import json
from datetime import date
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from temple_project.apps.reservations.models import Reservation


@login_required
def export_csv(request):
    """Export CSV des réservations selon filtres"""
    qs = _get_queryset_from_request(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="reservations.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Date", "Heure début", "Heure fin", "Loge", "Obédience",
        "Temple", "Type", "Sous-type", "Statut", "Agapes", "Nb repas",
        "Demandeur", "Email"
    ])
    for r in qs:
        writer.writerow([
            r.date, r.heure_debut, r.heure_fin,
            r.loge.nom, r.loge.obedience.nom, str(r.temple),
            r.get_type_reservation_display(), r.get_sous_type_display(),
            r.get_statut_display(), "Oui" if r.besoin_agapes else "Non",
            r.nombre_repas, r.nom_demandeur, r.email_demandeur,
        ])
    return response


@login_required
def export_excel(request):
    """Export Excel avec mise en forme"""
    qs = _get_queryset_from_request(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Réservations"

    headers = [
        "Date", "Heure début", "Heure fin", "Loge", "Obédience",
        "Temple", "Type", "Sous-type", "Statut", "Agapes", "Nb repas",
    ]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2C3E50")

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    STATUT_COLORS = {
        "validee": "C8E6C9",
        "attente": "FFF9C4",
        "refusee": "FFCDD2",
    }

    for row_idx, r in enumerate(qs, 2):
        data = [
            r.date, str(r.heure_debut), str(r.heure_fin),
            r.loge.nom, r.loge.obedience.nom, str(r.temple),
            r.get_type_reservation_display(), r.get_sous_type_display(),
            r.get_statut_display(), "Oui" if r.besoin_agapes else "Non",
            r.nombre_repas,
        ]
        fill_color = STATUT_COLORS.get(r.statut, "FFFFFF")
        fill = PatternFill("solid", fgColor=fill_color)
        for col_idx, value in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = fill

    # Ajustement largeur colonnes
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="reservations.xlsx"'
    return response


@login_required
def reporting(request):
    """Page de reporting et statistiques"""
    from django.db.models import Count, Sum
    from datetime import datetime

    # Saison : sept. annee → juin annee+1
    current_year = date.today().year
    # Déduire la saison courante : si on est avant septembre, la saison a démarré l'année précédente
    default_saison = current_year if date.today().month >= 9 else current_year - 1
    annee_saison = int(request.GET.get("annee", default_saison))

    saison_debut = date(annee_saison, 9, 1)
    saison_fin   = date(annee_saison + 1, 6, 30)

    reservations = Reservation.objects.filter(date__gte=saison_debut, date__lte=saison_fin)

    total      = reservations.count()
    validees   = reservations.filter(statut="validee").count()
    attente    = reservations.filter(statut="attente").count()
    refusees   = reservations.filter(statut="refusee").count()
    total_repas = reservations.filter(besoin_agapes=True, statut="validee").aggregate(
        s=Sum("nombre_repas")
    )["s"] or 0

    stats = {
        "total": total,
        "validees": validees,
        "attente": attente,
        "refusees": refusees,
        "total_repas": total_repas,
        "taux_validation": round(validees / total * 100, 1) if total > 0 else 0,
    }

    # Réservations par obédience (toute la saison, tous statuts)
    reservations_par_obedience = reservations.values(
        'loge__obedience__nom'
    ).annotate(
        nb_reservations=Count('id')
    ).order_by('-nb_reservations')[:10]

    # Graphique mensuel : mois de la saison (sept → juin), tous statuts
    reservations_par_mois = []
    mois_saison = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
    for m in mois_saison:
        annee_mois = annee_saison if m >= 9 else annee_saison + 1
        count = reservations.filter(date__year=annee_mois, date__month=m).count()
        reservations_par_mois.append({
            'mois': f'{annee_mois}-{m:02d}',
            'count': count,
        })

    # Réservations par temple (tous statuts)
    reservations_par_temple = reservations.values(
        'temple__nom'
    ).annotate(
        nb_reservations=Count('id')
    ).order_by('-nb_reservations')

    reservations_par_mois_json = json.dumps(reservations_par_mois)
    reservations_par_temple_json = json.dumps([
        {'nom': t['temple__nom'] or 'Non renseigné', 'nb_reservations': t['nb_reservations']}
        for t in reservations_par_temple
    ])

    context = {
        "stats": stats,
        "annee": annee_saison,
        "annee_courante": default_saison,
        "saison_label": f"{annee_saison}–{annee_saison + 1}",
        "reservations_par_obedience": reservations_par_obedience,
        "reservations_par_mois": reservations_par_mois_json,
        "reservations_par_temple": reservations_par_temple_json,
    }

    return render(request, "exports/reporting.html", context)


def _get_queryset_from_request(request):
    qs = Reservation.objects.select_related("loge", "loge__obedience", "temple")
    if request.GET.get("mois"):
        qs = qs.filter(date__month=request.GET["mois"])
    if request.GET.get("annee"):
        qs = qs.filter(date__year=request.GET["annee"])
    if request.GET.get("temple"):
        qs = qs.filter(temple_id=request.GET["temple"])
    if request.GET.get("loge"):
        qs = qs.filter(loge_id=request.GET["loge"])
    return qs.order_by("date", "heure_debut")
