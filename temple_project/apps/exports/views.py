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
from datetime import timedelta
from temple_project.apps.reservations.models import Reservation, Temple


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
        "temples": Temple.objects.all().order_by('nom'),
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


@login_required
def planning_pdf(request):
    """Export PDF du planning mensuel des tenues, par temple."""
    from io import BytesIO
    import calendar as _cal
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    today    = date.today()
    mois_p   = int(request.GET.get('mois',   today.month))
    annee_p  = int(request.GET.get('annee',  today.year))
    temple_p = request.GET.get('temple') or None

    MOIS_NOMS = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                 7:'Juillet',8:'Août',9:'Septembre',10:'Octobre',
                 11:'Novembre',12:'Décembre'}
    JOURS_FR  = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']

    debut = date(annee_p, mois_p, 1)
    fin   = date(annee_p, mois_p, _cal.monthrange(annee_p, mois_p)[1])

    if temple_p:
        temples = list(Temple.objects.filter(pk=temple_p))
    else:
        temples = list(Temple.objects.all().order_by('nom'))

    C_NAVY  = colors.HexColor('#0F2137')
    C_GOLD  = colors.HexColor('#C8A84B')
    C_LIGHT = colors.HexColor('#F8FAFC')
    C_ROW2  = colors.HexColor('#EFF6FF')

    sty_h1   = ParagraphStyle('h1',  fontName='Helvetica-Bold', fontSize=14,
                               textColor=C_NAVY, spaceAfter=2)
    sty_h2   = ParagraphStyle('h2',  fontName='Helvetica-Bold', fontSize=11,
                               textColor=C_GOLD, spaceAfter=6)
    sty_sub  = ParagraphStyle('sub', fontName='Helvetica',      fontSize=9,
                               textColor=colors.grey, spaceAfter=10)
    sty_pied = ParagraphStyle('pied',fontName='Helvetica',      fontSize=7,
                               textColor=colors.grey, alignment=TA_CENTER)
    sty_vide = ParagraphStyle('vide',fontName='Helvetica-Oblique', fontSize=9,
                               textColor=colors.grey, alignment=TA_CENTER)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
    )

    col_widths = [2.2*cm, 1.4*cm, 5.0*cm, 2.8*cm, 2.8*cm, 1.8*cm]
    headers    = ['Date', 'Jour', 'Loge', 'Horaires', 'Type', 'Agapes']

    def _table_temple(temple):
        tenues = (
            Reservation.objects
            .select_related('loge', 'loge__obedience', 'temple')
            .filter(
                temple=temple,
                statut='validee',
                date__gte=debut,
                date__lte=fin,
            )
            .order_by('date', 'heure_debut')
        )
        rows = [headers]
        for t in tenues:
            loge_nom = (t.loge.nom if t.loge
                        else (t.nom_organisation if hasattr(t, 'nom_organisation') else '—'))
            agapes = f"Oui – {t.nombre_repas} cvts" if t.besoin_agapes else 'Non'
            rows.append([
                t.date.strftime('%d/%m/%Y'),
                JOURS_FR[t.date.weekday()],
                loge_nom,
                f"{t.heure_debut:%H:%M} – {t.heure_fin:%H:%M}",
                t.get_type_reservation_display(),
                agapes,
            ])
        return rows, tenues.count()

    story = []

    # En-tête global
    titre_periode = f"{MOIS_NOMS[mois_p]} {annee_p}"
    story.append(Paragraph(f"Kellermann — Planning des tenues", sty_h1))
    story.append(Paragraph(titre_periode, sty_h2))
    story.append(Spacer(1, 0.2*cm))

    for i, temple in enumerate(temples):
        rows, nb = _table_temple(temple)

        story.append(Paragraph(str(temple), ParagraphStyle(
            'tnom', fontName='Helvetica-Bold', fontSize=10,
            textColor=C_NAVY, spaceAfter=3,
        )))
        story.append(Paragraph(f"{nb} tenue{'s' if nb != 1 else ''}", sty_sub))

        if nb == 0:
            story.append(Paragraph("Aucune tenue ce mois-ci.", sty_vide))
        else:
            n = len(rows)
            tbl = Table(rows, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0,0),  (-1,0),   C_NAVY),
                ('TEXTCOLOR',     (0,0),  (-1,0),   C_GOLD),
                ('FONTNAME',      (0,0),  (-1,0),   'Helvetica-Bold'),
                ('FONTSIZE',      (0,0),  (-1,0),   8),
                ('ALIGN',         (0,0),  (-1,0),   'CENTER'),
                ('TOPPADDING',    (0,0),  (-1,0),   5),
                ('BOTTOMPADDING', (0,0),  (-1,0),   5),
                ('FONTNAME',      (0,1),  (-1,n-1), 'Helvetica'),
                ('FONTSIZE',      (0,1),  (-1,n-1), 8),
                ('ROWBACKGROUNDS',(0,1),  (-1,n-1), [colors.white, C_LIGHT]),
                ('TOPPADDING',    (0,1),  (-1,n-1), 4),
                ('BOTTOMPADDING', (0,1),  (-1,n-1), 4),
                ('ALIGN',         (1,1),  (1,n-1),  'CENTER'),  # Jour
                ('ALIGN',         (3,1),  (3,n-1),  'CENTER'),  # Horaires
                ('ALIGN',         (5,1),  (5,n-1),  'CENTER'),  # Agapes
                ('GRID',          (0,0),  (-1,-1),  0.4, colors.HexColor('#CBD5E1')),
                ('BOX',           (0,0),  (-1,-1),  1,   C_NAVY),
            ]))
            story.append(tbl)

        if i < len(temples) - 1:
            story.append(Spacer(1, 0.5*cm))
            story.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.HexColor('#E2E8F0')))
            story.append(Spacer(1, 0.3*cm))

    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph(
        f"Généré le {today.strftime('%d/%m/%Y')} — Temples Kellermann",
        sty_pied,
    ))

    doc.build(story)
    buf.seek(0)
    nom = f"planning_{annee_p}_{mois_p:02d}"
    if temple_p and temples:
        nom += f"_{temples[0].nom.replace(' ', '_')}"
    nom += ".pdf"
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom}"'
    return response
