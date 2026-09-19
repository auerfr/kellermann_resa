from django.shortcuts import render
from temple_project.apps.auth_custom.views import membre_required
from django.http import JsonResponse
from django.db.models import Q
from datetime import date, timedelta
import calendar
from collections import defaultdict

from temple_project.apps.reservations.models import (
    Reservation, Temple, Indisponibilite,
    SalleReunion, ReservationSalle, BlocageCreneaux,
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
            a_reconfirmer = bool(r.loge and r.loge.statut == 'a_reconfirmer')
            titre = f"{(r.loge.abreviation or r.loge.nom) if r.loge else (r.nom_organisation or '?')}"
            if a_reconfirmer:
                color = {"bg": "#F1F5F9", "border": "#CBD5E1", "text": "#64748B"}
                titre += " (à reconfirmer)"
            events.append({
                "id":    f"t-{r.pk}",
                "title": titre,
                "start": f"{r.date}T{r.heure_debut}",
                "end":   f"{r.date}T{r.heure_fin}",
                "backgroundColor": color["bg"],
                "borderColor":     color["border"],
                "textColor":       color["text"],
                "extendedProps": {
                    "type":       "temple",
                    "a_reconfirmer": a_reconfirmer,
                    "creneau":    _creneau(r.heure_debut),
                    "heure":      _heure_court(r.heure_debut),
                    "temple":     str(r.temple),
                    "loge":       r.loge.nom if r.loge else (r.nom_organisation or '?'),
                    "loge_nom":   r.loge.nom if r.loge else (r.nom_organisation or '?'),
                    "loge_court": _loge_court(r.loge) if r.loge else (r.nom_organisation or '?'),
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
        qs_salles = ReservationSalle.objects.select_related("salle", "loge").filter(
            date__gte=start, date__lte=end, statut__in=("validee", "attente")
        )
        # Mêmes filtres que pour les temples : loge / obédience
        if loge_id:
            qs_salles = qs_salles.filter(loge_id=loge_id)
        elif obd_id:
            qs_salles = qs_salles.filter(loge__obedience_id=obd_id)
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
            a_reconfirmer = bool(rs.loge and rs.loge.statut == 'a_reconfirmer')
            if ts == "cabinet_reflexion":
                title = f"\U0001f6aa {org} \u2013 Cabinets"
            elif ts == "agapes":
                if rs.type_reunion == 'banquet':
                    title = f"\U0001f37d {org} \u2013 Banquet"
                else:
                    title = f"\U0001fa91 {org} \u2013 {rs.get_type_reunion_display()}"
                    couleur = _COULEURS_SALLE["reunion"][rs.statut]
            else:
                title = f"\U0001fa91 {org} \u2013 {rs.salle.nom}"
            if a_reconfirmer:
                couleur = {"bg": "#F1F5F9", "border": "#CBD5E1", "text": "#64748B"}
                title += " (\u00e0 reconfirmer)"
            props = {
                "type":         "salle",
                "a_reconfirmer": a_reconfirmer,
                "creneau":      _creneau(rs.heure_debut),
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

    # ── 4. Blocages traiteur ─────────────────────────────────────────────────
    blocages_qs = BlocageCreneaux.objects.filter(
        date__lte=end,
    ).filter(
        Q(date_fin__gte=start) | Q(date_fin__isnull=True, date__gte=start)
    ).prefetch_related("salles", "temples")

    for b in blocages_qs:
        b_fin = b.date_fin or b.date
        # Lieux concernés
        lieux = [str(s) for s in b.salles.all()] + [str(t) for t in b.temples.all()]
        lieux_label = ", ".join(lieux) if lieux else "Tous espaces"
        events.append({
            "id":              f"blocage-{b.pk}",
            "title":           f"🔒 Traiteur fermé — {b.motif}",
            "start":           str(b.date),
            "end":             str(b_fin + timedelta(days=1)),
            "allDay":          True,
            "backgroundColor": "#DC2626",
            "borderColor":     "#991B1B",
            "textColor":       "#FFFFFF",
            "extendedProps": {
                "type":        "blocage_traiteur",
                "motif":       b.motif,
                "heure_debut": str(b.heure_debut)[:5],
                "heure_fin":   str(b.heure_fin)[:5],
                "lieux":       lieux_label,
                "date_debut":  str(b.date),
                "date_fin":    str(b_fin),
            },
        })

    # ── 5. Jours fériés et vacances scolaires Zone B ─────────────────────────
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

def _creneau(heure):
    """Retourne 'matin', 'aprem' ou 'soir' selon l'heure de début."""
    h = heure.hour
    if h < 12:
        return "matin"
    elif h < 18:
        return "aprem"
    else:
        return "soir"


def _heure_court(t):
    """Format '19h' ou '19h30' selon les minutes."""
    if t.minute == 0:
        return f"{t.hour}h"
    return f"{t.hour}h{t.minute:02d}"


def _loge_court(loge):
    """Abréviation si disponible, sinon 2-3 premiers mots du nom."""
    if loge is None:
        return '?'
    if loge.abreviation:
        return loge.abreviation
    mots = loge.nom.split()
    return ' '.join(mots[:3])


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



def calendrier_annuel(request):
    """Calendrier annuel A3 — grille mois × temple, accessible à tous."""
    today = date.today()

    annee_param = request.GET.get('annee', '')
    debut = int(annee_param) if annee_param.isdigit() else (today.year if today.month >= 9 else today.year - 1)
    fin   = debut + 1

    MOIS_SAISON = [
        (debut, 9), (debut, 10), (debut, 11), (debut, 12),
        (fin,   1), (fin,   2),  (fin,   3),  (fin,   4), (fin, 5), (fin, 6),
    ]
    MOIS_NOM = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 9: 'Septembre', 10: 'Octobre',
        11: 'Novembre', 12: 'Décembre',
    }
    JOURS_FR  = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
    FERIES_FR = {(1,1),(5,1),(5,8),(7,14),(8,15),(11,1),(11,11),(12,25)}

    temples = list(Temple.objects.all().order_by('nom'))
    d_debut = date(debut, 9, 1)
    d_fin   = date(fin,   6, 30)

    resa_idx = defaultdict(lambda: defaultdict(list))
    for r in (Reservation.objects
              .filter(statut='validee', date__gte=d_debut, date__lte=d_fin)
              .select_related('loge', 'temple').order_by('date', 'heure_debut')):
        if not r.temple:
            continue
        abbr = (r.loge.abreviation or r.loge.nom[:4]) if r.loge else '?'
        resa_idx[r.date][r.temple.pk].append(abbr)

    bq_idx = defaultdict(list)
    for s in (ReservationSalle.objects
              .filter(statut='validee', date__gte=d_debut, date__lte=d_fin)
              .select_related('loge').order_by('date')):
        abbr = (s.loge.abreviation or s.loge.nom[:4]) if s.loge else '?'
        bq_idx[s.date].append(abbr)

    rows = []
    for jour in range(1, 32):
        cells = []
        for annee, mois in MOIS_SAISON:
            _, nb_j = calendar.monthrange(annee, mois)
            if jour > nb_j:
                cells.append(None)
            else:
                d = date(annee, mois, jour)
                cells.append({
                    'j':  JOURS_FR[d.weekday()],
                    'we': d.weekday() >= 5,
                    'fer': (mois, jour) in FERIES_FR,
                    'nt': d == today,
                    'tv': [' '.join(resa_idx[d].get(t.pk, [])) for t in temples],
                    'bq': ' '.join(bq_idx.get(d, [])),
                })
        rows.append({'n': jour, 'c': cells})

    mois_headers = [
        {'nom': MOIS_NOM[m], 'annee': a, 'cols': 1 + len(temples)}
        for a, m in MOIS_SAISON
    ]
    loges_legende = (Loge.objects
                     .filter(reservations__date__gte=d_debut, reservations__date__lte=d_fin, reservations__statut='validee')
                     .distinct().order_by('abreviation', 'nom'))

    return render(request, 'calendrier/calendrier_annuel.html', {
        'rows': rows, 'temples': temples, 'mois_headers': mois_headers,
        'loges_legende': loges_legende,
        'debut': debut, 'fin': fin, 'prec': debut - 1, 'suiv': debut + 1,
        'today': today,
    })
