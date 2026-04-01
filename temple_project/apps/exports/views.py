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
    year = int(request.GET.get("annee", date.today().year))
    reservations = Reservation.objects.filter(date__year=year)

    stats = {
        "total": reservations.count(),
        "validees": reservations.filter(statut="validee").count(),
        "attente": reservations.filter(statut="attente").count(),
        "refusees": reservations.filter(statut="refusee").count(),
        "total_repas": sum(r.nombre_repas for r in reservations.filter(besoin_agapes=True, statut="validee")),
        "taux_validation": round(reservations.filter(statut="validee").count() / reservations.count() * 100, 1) if reservations.count() > 0 else 0,
    }

    # Réservations par obédience
    from django.db.models import Count
    reservations_par_obedience = Reservation.objects.filter(date__year=year).values(
        'loge__obedience__nom'
    ).annotate(
        nb_reservations=Count('id')
    ).order_by('-nb_reservations')[:10]

    # Réservations par mois (12 derniers mois)
    from datetime import datetime, timedelta
    today = datetime.now()
    reservations_par_mois = []
    for i in range(11, -1, -1):
        date_check = today - timedelta(days=30*i)
        mois = date_check.strftime('%Y-%m')
        count = Reservation.objects.filter(
            date__year=date_check.year,
            date__month=date_check.month,
            statut='validee'
        ).count()
        reservations_par_mois.append({
            'mois': mois,
            'count': count
        })

    # Réservations par temple
    reservations_par_temple = Reservation.objects.filter(date__year=year).values(
        'temple__nom'
    ).annotate(
        nb_reservations=Count('id')
    ).order_by('-nb_reservations')

    # Convertir en JSON sérialisable
    reservations_par_mois_json = json.dumps(reservations_par_mois)
    reservations_par_temple_json = json.dumps([
        {'nom': t['temple__nom'], 'nb_reservations': t['nb_reservations']}
        for t in reservations_par_temple
    ])

    context = {
        "stats": stats,
        "annee": year,
        "annee_courante": date.today().year,
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
