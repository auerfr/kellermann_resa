from django.shortcuts import render
from temple_project.apps.auth_custom.views import membre_required
from django.http import JsonResponse
from django.db.models import Q
from datetime import date
import calendar

from temple_project.apps.reservations.models import (
    Reservation, Temple, Indisponibilite,
    SalleReunion, ReservationSalle,
)
from temple_project.apps.loges.models import Loge, Obedience


def calendrier_principal(request):
    """Vue principale du calendrier — accessible avec mot de passe annuel."""
    temples    = Temple.objects.all()
    loges      = Loge.objects.filter(actif=True).select_related("obedience").order_by("nom")
    obediences = Obedience.objects.all().order_by("nom")
    salles     = SalleReunion.objects.filter(actif=True)

    context = {
        "temples":    temples,
        "loges":      loges,
        "obediences": obediences,
        "salles":     salles,
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
    if type_filtre != "salle":
        for r in qs:
            color = _couleur_reservation(r)
            events.append({
                "id":    f"t-{r.pk}",
                "title": f"{r.loge.abreviation or r.loge.nom}",
                "start": f"{r.date}T{r.heure_debut}",
                "end":   f"{r.date}T{r.heure_fin}",
                "backgroundColor": color["bg"],
                "borderColor":     color["border"],
                "textColor":       color["text"],
                "extendedProps": {
                    "type":       "temple",
                    "temple":     str(r.temple),
                    "loge":       r.loge.nom,
                    "obedience":  r.loge.obedience.nom,
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
    if type_filtre in (None, "all", "salle"):
        qs_salles = ReservationSalle.objects.select_related("salle").filter(
            date__gte=start, date__lte=end, statut="validee"
        )
        for rs in qs_salles:
            events.append({
                "id":    f"s-{rs.pk}",
                "title": f"{rs.salle.nom} · {rs.organisation or rs.nom_demandeur}",
                "start": f"{rs.date}T{rs.heure_debut}",
                "end":   f"{rs.date}T{rs.heure_fin}",
                "backgroundColor": "#F3E8FF",
                "borderColor":     "#9333EA",
                "textColor":       "#581C87",
                "extendedProps": {
                    "type":        "salle",
                    "salle":       str(rs.salle),
                    "objet":       rs.objet,
                    "organisation":rs.organisation,
                    "participants":rs.nombre_participants,
                    "horaires":    f"{rs.heure_debut:%H:%M} – {rs.heure_fin:%H:%M}",
                    "statut":      rs.statut,
                    "uuid":        str(rs.uuid),
                },
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
            "loge":     r.loge.nom,
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
    # Validée
    if r.loge.type_loge == "haut_grade":
        return {"bg": "#F0FDF4", "border": "#4ADE80", "text": "#14532D"}
    return {"bg": "#EFF6FF", "border": "#60A5FA", "text": "#1E3A8A"}

