from django.shortcuts import render
from temple_project.apps.auth_custom.views import membre_required
from django.http import JsonResponse
from django.db.models import Q
from datetime import date, timedelta
import calendar

from temple_project.apps.reservations.models import (
    Reservation, Temple, Indisponibilite,
    SalleReunion, ReservationSalle,
)
from temple_project.apps.loges.models import Loge, Obedience


def calendrier_principal(request):
    """Vue principale du calendrier — accessible avec mot de passe annuel."""
    today      = date.today()
    temples    = Temple.objects.all()
    loges      = Loge.objects.filter(actif=True).select_related("obedience").order_by("nom")
    obediences = Obedience.objects.all().order_by("nom")
    salles     = SalleReunion.objects.filter(actif=True)

    context = {
        "temples":       temples,
        "loges":         loges,
        "obediences":    obediences,
        "salles":        salles,
        "annee_courante": today.year if today.month >= 9 else today.year - 1,
    }
    return render(request, "calendrier/principal.html", context)


def api_evenements(request):
    """
    API JSON pour FullCalendar.
    Retourne : réservations temples + réservations salles + indisponibilités.
    Paramètres GET : start, end, temple, loge, obedience, type
    """
    start      = request.GET.get("start", "")[:10]
    end        = request.GET.get("end",   "")[:10]
    temple_id  = request.GET.get("temple")
    loge_id    = request.GET.get("loge")
    obd_id     = request.GET.get("obedience")
    type_filtre = request.GET.get("type")   # reguliere | exceptionnelle | salle | all

    events = []

    # ── 1. Réservations de temples ────────────────────────────────────────────
    qs = Reservation.objects.select_related(
        "loge", "loge__obedience", "temple"
    ).filter(date__gte=start, date__lte=end)

    if temple_id:
        qs = qs.filter(temple_id=temple_id)
    if loge_id:
        qs = qs.filter(loge_id=loge_id)
    if obd_id:
        qs = qs.filter(loge__obedience_id=obd_id)
    if type_filtre in ("reguliere", "exceptionnelle"):
        qs = qs.filter(type_reservation=type_filtre)
    if type_filtre not in ("salle", "cabinet", "banquet"):
        for r in qs:
            color = _couleur_reservation(r)
            events.append({
                "id":    f"t-{r.pk}",
                "title": f"{(r.loge.abreviation or r.loge.nom) if r.loge else (r.nom_organisation or '?')}",
                "start": f"{r.date}T{r.heure_debut}",
                "end":   f"{r.date}T{r.heure_fin}",
                "backgroundColor": color["bg"],
                "borderColor":     color["border"],
                "textColor":       color["text"],
                "extendedProps": {
                    "type":       "temple",
                    "temple":     str(r.temple),
                    "loge":       r.loge.nom if r.loge else (r.nom_organisation or '?'),
                    "obedience":  r.loge.obedience.nom if r.loge else '—',
                    "type_res":   r.get_type_reservation_display(),
                    "sous_type":  r.get_sous_type_display(),
                    "statut":     r.statut,
                    "statut_label": r.get_statut_display(),
                    "agapes":     r.besoin_agapes,
                    "repas":      r.nombre_repas,
                    "horaires":   f"{r.heure_debut:%H:%M} – {r.heure_fin:%H:%M}",
                    "demandeur":  r.nom_demandeur,
                    "uuid":       str(r.uuid),
                },
            })

    # ── 2. Réservations de salles ─────────────────────────────────────────────
    if type_filtre not in ("reguliere", "exceptionnelle"):
        _COULEURS_SALLE = {
            "cabinet_reflexion": {
                "validee": {"bg": "#FFF7ED", "border": "#EA580C", "text": "#7C2D12"},
                "attente": {"bg": "#FEF9C3", "border": "#F59E0B", "text": "#92400E"},
            },
            "agapes": {
                "validee": {"bg": "#FFF1F2", "border": "#BE123C", "text": "#881337"},
                "attente": {"bg": "#FFE4E6", "border": "#F87171", "text": "#9F1239"},
            },
            "reunion": {
                "validee": {"bg": "#F3E8FF", "border": "#9333EA", "text": "#581C87"},
                "attente": {"bg": "#F5F3FF", "border": "#A78BFA", "text": "#4C1D95"},
            },
        }
        qs_salles = ReservationSalle.objects.select_related("salle").filter(
            date__gte=start, date__lte=end, statut__in=("validee", "attente")
        )
        if type_filtre == "cabinet":
            qs_salles = qs_salles.filter(salle__type_salle="cabinet_reflexion")
        elif type_filtre == "banquet":
            qs_salles = qs_salles.filter(salle__type_salle="agapes")
        elif type_filtre == "salle":
            qs_salles = qs_salles.filter(salle__type_salle="reunion")
        for rs in qs_salles:
            ts = rs.salle.type_salle
            couleur = _COULEURS_SALLE.get(ts, _COULEURS_SALLE["reunion"])[rs.statut]
            org = rs.organisation or rs.nom_demandeur
            if ts == "cabinet_reflexion":
                title = f"\U0001f6aa {org} \u2013 Cabinets"
            elif ts == "agapes":
                title = f"\U0001f37d {org} \u2013 Banquet"
            else:
                title = f"\U0001fa91 {org} \u2013 {rs.salle.nom}"
            props = {
                "type":         "salle",
                "type_salle":   ts,
                "salle":        str(rs.salle),
                "objet":        rs.objet,
                "organisation": rs.organisation,
                "participants": rs.nombre_participants,
                "horaires":     f"{rs.heure_debut:%H:%M} \u2013 {rs.heure_fin:%H:%M}",
                "statut":       rs.statut,
                "uuid":         str(rs.uuid),
            }
            if ts == "cabinet_reflexion":
                props["nombre_cabinets"] = rs.nombre_cabinets
            events.append({
                "id":              f"s-{rs.pk}",
                "title":           title,
                "start":           f"{rs.date}T{rs.heure_debut}",
                "end":             f"{rs.date}T{rs.heure_fin}",
                "backgroundColor": couleur["bg"],
                "borderColor":     couleur["border"],
                "textColor":       couleur["text"],
                "extendedProps":   props,
            })

    # ── 3. Indisponibilités ───────────────────────────────────────────────────
    indispos = Indisponibilite.objects.filter(
        date_debut__lte=end, date_fin__gte=start
    ).prefetch_related("temples", "salles")

    for indispo in indispos:
        temples_touches = [str(t) for t in indispo.temples.all()]
        salles_touchees = [str(s) for s in indispo.salles.all()]
        label_lieux = ", ".join(temples_touches + salles_touchees) or "Tous espaces"
        events.append({
            "id":    f"i-{indispo.pk}",
            "title": f"Indispo – {label_lieux}",
            "start": str(indispo.date_debut),
            "end":   str(indispo.date_fin),
            "allDay": True,
            "backgroundColor": "#1E293B",
            "borderColor":     "#0F172A",
            "textColor":       "#94A3B8",
            "display": "background",
            "extendedProps": {
                "type":   "indisponibilite",
                "motif":  indispo.motif,
                "lieux":  label_lieux,
            },
        })

    # ── 4. Jours fériés et vacances scolaires Zone B ─────────────────────────
    if request.GET.get("conges", "1") != "0":
        annee_debut = int(start[:4]) if start else date.today().year
        annee_fin   = int(end[:4])   if end   else date.today().year
        for annee in range(annee_debut, annee_fin + 1):
            for ev in _feries(annee):
                d = ev["date"]
                if str(d) >= start and str(d) <= end:
                    events.append({
                        "id":    f"ferie-{d}",
                        "title": ev["label"],
                        "start": str(d),
                        "allDay": True,
                        "display": "background",
                        "backgroundColor": "#FEF9C3",
                        "borderColor":     "#CA8A04",
                        "extendedProps": {"type": "ferie"},
                    })
            for ev in _vacances_zone_b(annee):
                d_start = str(ev["debut"])
                d_end   = str(ev["fin"] + timedelta(days=1))
                if d_start <= end and d_end >= start:
                    events.append({
                        "id":    f"vac-{ev['debut']}-{ev['fin']}",
                        "title": ev["label"],
                        "start": d_start,
                        "end":   d_end,
                        "allDay": True,
                        "display": "background",
                        "backgroundColor": "#DCFCE7",
                        "borderColor":     "#16A34A",
                        "extendedProps": {"type": "vacances"},
                    })

    return JsonResponse(events, safe=False)


def api_disponibilites(request):
    """
    API de disponibilité des espaces sur un créneau.
    Paramètres GET : date, heure_debut, heure_fin
    Retourne la liste des temples et salles libres/occupés.
    """
    date_str    = request.GET.get("date")
    heure_debut = request.GET.get("heure_debut", "19:00")
    heure_fin   = request.GET.get("heure_fin",   "23:00")

    if not date_str:
        return JsonResponse({"error": "Paramètre date manquant"}, status=400)

    # Temples occupés sur ce créneau
    reservations = Reservation.objects.filter(
        date=date_str,
        statut__in=["validee", "attente"],
        heure_debut__lt=heure_fin,
        heure_fin__gt=heure_debut,
    ).select_related("temple", "loge")

    temples_occupes = {}
    for r in reservations:
        temples_occupes[r.temple.nom] = {
            "loge":     r.loge.nom if r.loge else (r.nom_organisation or r.nom_demandeur),
            "horaires": f"{r.heure_debut:%H:%M}–{r.heure_fin:%H:%M}",
            "statut":   r.statut,
        }

    # Salles occupées sur ce créneau
    resa_salles = ReservationSalle.objects.filter(
        date=date_str,
        statut__in=["validee", "attente"],
        heure_debut__lt=heure_fin,
        heure_fin__gt=heure_debut,
    ).select_related("salle")

    salles_occupees = {}
    for rs in resa_salles:
        salles_occupees[rs.salle.pk] = {
            "organisation": rs.organisation or rs.nom_demandeur,
            "horaires":     f"{rs.heure_debut:%H:%M}–{rs.heure_fin:%H:%M}",
            "statut":       rs.statut,
        }

    # Résultat temples
    temples_result = []
    for temple in Temple.objects.all():
        occ = temples_occupes.get(temple.nom)
        temples_result.append({
            "id":        temple.pk,
            "nom":       str(temple),
            "capacite":  temple.capacite,
            "libre":     occ is None,
            "occupation": occ,
        })

    # Résultat salles
    salles_result = []
    for salle in SalleReunion.objects.filter(actif=True):
        occ = salles_occupees.get(salle.pk)
        salles_result.append({
            "id":        salle.pk,
            "nom":       str(salle),
            "type_salle": salle.type_salle,
            "capacite":  salle.capacite,
            "libre":     occ is None,
            "occupation": occ,
        })

    return JsonResponse({
        "date":        date_str,
        "heure_debut": heure_debut,
        "heure_fin":   heure_fin,
        "temples":     temples_result,
        "salles":      salles_result,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _couleur_reservation(r):
    """Retourne bg/border/text selon le type et statut de la réservation."""
    if r.statut == "attente":
        return {"bg": "#FFFBEB", "border": "#F59E0B", "text": "#92400E"}
    if r.statut == "refusee":
        return {"bg": "#FFF1F2", "border": "#FB7185", "text": "#881337"}
    # Validée — Congrès / Session régionale
    if r.type_reservation == "congres":
        return {"bg": "#F5F3FF", "border": "#8B5CF6", "text": "#4C1D95"}
    # Validée — Haut grade
    if r.loge and r.loge.type_loge == "haut_grade":
        return {"bg": "#F0FDF4", "border": "#4ADE80", "text": "#14532D"}
    return {"bg": "#EFF6FF", "border": "#60A5FA", "text": "#1E3A8A"}


def _paques(annee):
    """Calcule la date de Pâques (algorithme anonyme grégorien)."""
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(114 + h + l - 7 * m, 31)
    return date(annee, month, day + 1)


def _feries(annee):
    """Retourne la liste des jours fériés français pour une année."""
    paques = _paques(annee)
    return [
        {"date": date(annee, 1, 1),   "label": "Jour de l'an"},
        {"date": paques + timedelta(days=1), "label": "Lundi de Pâques"},
        {"date": date(annee, 5, 1),   "label": "Fête du Travail"},
        {"date": date(annee, 5, 8),   "label": "Victoire 1945"},
        {"date": paques + timedelta(days=39), "label": "Ascension"},
        {"date": paques + timedelta(days=50), "label": "Lundi de Pentecôte"},
        {"date": date(annee, 7, 14),  "label": "Fête Nationale"},
        {"date": date(annee, 8, 15),  "label": "Assomption"},
        {"date": date(annee, 11, 1),  "label": "Toussaint"},
        {"date": date(annee, 11, 11), "label": "Armistice"},
        {"date": date(annee, 12, 25), "label": "Noël"},
    ]


def _vacances_zone_b(annee):
    """
    Vacances scolaires Zone B (académie Nancy-Metz) pour l'année civile donnée.
    Couvre la saison scolaire annee-1/annee et annee/annee+1.
    """
    PERIODES = {
        # saison 2024-2025
        2024: [
            {"label": "Toussaint 2024",  "debut": date(2024, 10, 19), "fin": date(2024, 11,  3)},
            {"label": "Noël 2024-2025",  "debut": date(2024, 12, 21), "fin": date(2025,  1,  5)},
        ],
        2025: [
            {"label": "Hiver 2025",      "debut": date(2025,  2, 22), "fin": date(2025,  3,  9)},
            {"label": "Printemps 2025",  "debut": date(2025,  4, 19), "fin": date(2025,  5,  4)},
            {"label": "Été 2025",        "debut": date(2025,  7,  5), "fin": date(2025,  9,  1)},
            {"label": "Toussaint 2025",  "debut": date(2025, 10, 18), "fin": date(2025, 11,  2)},
            {"label": "Noël 2025-2026",  "debut": date(2025, 12, 20), "fin": date(2026,  1,  4)},
        ],
        2026: [
            {"label": "Hiver 2026",      "debut": date(2026,  2, 14), "fin": date(2026,  3,  1)},
            {"label": "Printemps 2026",  "debut": date(2026,  4, 18), "fin": date(2026,  5,  3)},
            {"label": "Été 2026",        "debut": date(2026,  7,  4), "fin": date(2026,  9,  1)},
            {"label": "Toussaint 2026",  "debut": date(2026, 10, 17), "fin": date(2026, 11,  1)},
            {"label": "Noël 2026-2027",  "debut": date(2026, 12, 19), "fin": date(2027,  1,  3)},
        ],
        2027: [
            {"label": "Hiver 2027",      "debut": date(2027,  2, 13), "fin": date(2027,  2, 28)},
            {"label": "Printemps 2027",  "debut": date(2027,  4, 17), "fin": date(2027,  5,  2)},
            {"label": "Été 2027",        "debut": date(2027,  7,  3), "fin": date(2027,  9,  1)},
        ],
    }
    return PERIODES.get(annee, [])

