from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date, timedelta
import calendar

from temple_project.apps.reservations.models import (
    Reservation, ReservationSalle, SalleReunion, BlocageCreneaux
)
from temple_project.apps.loges.models import Loge
from .forms import (
    ReservationDirecteForm, TraiteurReservationDirecteForm,
    BlocageCreneauxForm, NotificationCouvertsForm,
)
from .models import NotificationCouverts


# ── Décorateurs d'accès ───────────────────────────────────────────────────────

def traiteur_required(view_func):
    """Décorateur : autorise uniquement les membres du groupe Traiteur (et les admins)."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_staff
            or request.user.groups.filter(name="Traiteur").exists()
        ):
            return view_func(request, *args, **kwargs)
        return redirect(f"/auth/traiteur/?next={request.path}")

    return wrapper


def membre_ou_traiteur_required(view_func):
    """Décorateur : autorise les membres (cookie), traiteur et admins."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        est_staff    = request.user.is_authenticated and request.user.is_staff
        est_traiteur = request.user.is_authenticated and request.user.groups.filter(name="Traiteur").exists()
        est_membre   = request.COOKIES.get("kellermann_membre") == "1"
        if est_staff or est_traiteur or est_membre:
            return view_func(request, *args, **kwargs)
        return redirect(f"/auth/login/?next={request.path}")

    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nav_mois(annee, mois):
    """Retourne (mois_prec, annee_prec, mois_suiv, annee_suiv)."""
    if mois == 1:
        mp, ap = 12, annee - 1
    else:
        mp, ap = mois - 1, annee
    if mois == 12:
        ms, as_ = 1, annee + 1
    else:
        ms, as_ = mois + 1, annee
    return mp, ap, ms, as_


def _couverts_effectifs(r, loge=None):
    """Retourne (couverts, est_estimation) pour une réservation."""
    if hasattr(r, "nombre_repas"):
        couverts = r.nombre_repas
        loge_obj = r.loge
    else:
        couverts = r.nombre_participants
        loge_obj = None

    if couverts and couverts > 0:
        return couverts, False

    # Pas de couverts renseignés → essayer l'effectif moyen de la loge
    l = loge_obj or loge
    if l and hasattr(l, "effectif_moyen_agapes") and l.effectif_moyen_agapes:
        return l.effectif_moyen_agapes, True
    return 0, False


# ── Tableau de bord ───────────────────────────────────────────────────────────

@traiteur_required
def tableau_de_bord(request):
    today = date.today()
    prochaines_agapes = Reservation.objects.filter(
        statut="validee",
        besoin_agapes=True,
        date__gte=today,
        date__lte=today + timedelta(days=30),
    ).select_related("loge", "temple").order_by("date")

    blocages = BlocageCreneaux.objects.filter(
        date__gte=today
    ).prefetch_related("salles").order_by("date")[:5]

    # Notifications couverts non lues
    notifications = NotificationCouverts.objects.filter(
        statut="non_lu"
    ).select_related("loge").order_by("-created_at")

    context = {
        "prochaines_agapes":   prochaines_agapes,
        "nb_agapes_mois":      prochaines_agapes.count(),
        "blocages":            blocages,
        "notifications":       notifications,
        "nb_notifications":    notifications.count(),
        "today":               today,
    }
    return render(request, "traiteur/tableau_de_bord.html", context)


@traiteur_required
def marquer_notification_lue(request, pk):
    """Marquer une notification comme lue."""
    notif = get_object_or_404(NotificationCouverts, pk=pk)
    if request.method == "POST":
        notif.statut = "lu"
        notif.save()
    return redirect("traiteur:tableau_de_bord")


# ── Calendrier agapes ─────────────────────────────────────────────────────────

@traiteur_required
def calendrier(request):
    """Calendrier mensuel avec filtres et sélecteur mois/année."""
    today  = date.today()
    annee  = int(request.GET.get("annee", today.year))
    mois   = int(request.GET.get("mois",  today.month))
    filtre = request.GET.get("filtre", "tout")   # tout | agapes | blocages

    # Bornes mois
    mois_prec, annee_prec, mois_suiv, annee_suiv = _nav_mois(annee, mois)
    premier_jour = date(annee, mois, 1)
    dernier_jour = date(annee, mois, calendar.monthrange(annee, mois)[1])

    # Données
    reservations = Reservation.objects.filter(
        statut="validee",
        date__gte=premier_jour,
        date__lte=dernier_jour,
    ).select_related("loge", "temple").order_by("date", "heure_debut")

    reservations_salles = ReservationSalle.objects.filter(
        statut="validee",
        date__gte=premier_jour,
        date__lte=dernier_jour,
        salle__type_salle="agapes",
    ).select_related("salle").order_by("date", "heure_debut")

    blocages = BlocageCreneaux.objects.filter(
        date__gte=premier_jour,
        date__lte=dernier_jour,
    ).prefetch_related("salles").order_by("date", "heure_debut")

    # Application du filtre
    if filtre == "agapes":
        reservations = reservations.filter(besoin_agapes=True)
    elif filtre == "blocages":
        reservations        = reservations.none()
        reservations_salles = reservations_salles.none()

    # Construction events_by_date
    events_by_date = {}
    for r in reservations:
        couverts, est_estim = _couverts_effectifs(r)
        events_by_date.setdefault(r.date, []).append({
            "type":       "reservation",
            "obj":        r,
            "agapes":     r.besoin_agapes,
            "couverts":   couverts,
            "estimation": est_estim,
        })
    for r in reservations_salles:
        couverts, est_estim = _couverts_effectifs(r)
        events_by_date.setdefault(r.date, []).append({
            "type":       "salle",
            "obj":        r,
            "agapes":     True,
            "couverts":   couverts,
            "estimation": est_estim,
        })
    for b in blocages:
        events_by_date.setdefault(b.date, []).append({
            "type": "blocage", "obj": b, "agapes": False, "couverts": 0, "estimation": False,
        })

    # Sélecteur mois/année : 18 mois autour d'aujourd'hui
    mois_choices = []
    import locale
    for delta in range(-3, 15):
        m = today.month + delta
        y = today.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        mois_choices.append({
            "mois": m, "annee": y,
            "label": date(y, m, 1).strftime("%B %Y").capitalize(),
            "actif": m == mois and y == annee,
        })

    context = {
        "annee": annee, "mois": mois,
        "nom_mois":  premier_jour.strftime("%B %Y").capitalize(),
        "cal":       calendar.monthcalendar(annee, mois),
        "events_by_date": events_by_date,
        "today":     today,
        "mois_prec": mois_prec,  "annee_prec": annee_prec,
        "mois_suiv": mois_suiv,  "annee_suiv": annee_suiv,
        "filtre":    filtre,
        "mois_choices": mois_choices,
        # Listes pour tableau détaillé
        "reservations":        reservations,
        "reservations_salles": reservations_salles,
        "blocages":            blocages,
    }
    return render(request, "traiteur/calendrier.html", context)


# ── Planning mensuel ──────────────────────────────────────────────────────────

@traiteur_required
def planning(request):
    """Vue liste mensuelle de tous les repas avec couverts (et estimations)."""
    today = date.today()
    annee = int(request.GET.get("annee", today.year))
    mois  = int(request.GET.get("mois",  today.month))

    mois_prec, annee_prec, mois_suiv, annee_suiv = _nav_mois(annee, mois)
    premier_jour = date(annee, mois, 1)
    dernier_jour = date(annee, mois, calendar.monthrange(annee, mois)[1])

    agapes_temple = Reservation.objects.filter(
        statut="validee",
        besoin_agapes=True,
        date__gte=premier_jour,
        date__lte=dernier_jour,
    ).select_related("loge", "temple").order_by("date", "heure_debut")

    agapes_salles = ReservationSalle.objects.filter(
        statut="validee",
        date__gte=premier_jour,
        date__lte=dernier_jour,
        salle__type_salle="agapes",
    ).select_related("salle").order_by("date", "heure_debut")

    repas = []
    for r in agapes_temple:
        couverts, est_estim = _couverts_effectifs(r)
        repas.append({
            "date":        r.date,
            "heure_debut": r.heure_debut,
            "heure_fin":   r.heure_fin,
            "lieu":        str(r.temple),
            "organisation": r.loge.nom if r.loge else r.nom_organisation or r.nom_demandeur,
            "couverts":    couverts,
            "estimation":  est_estim,
            "type":        "Temple",
        })
    for r in agapes_salles:
        couverts, est_estim = _couverts_effectifs(r)
        repas.append({
            "date":        r.date,
            "heure_debut": r.heure_debut,
            "heure_fin":   r.heure_fin,
            "lieu":        str(r.salle),
            "organisation": r.organisation or r.nom_demandeur,
            "couverts":    couverts,
            "estimation":  est_estim,
            "type":        "Salle",
        })
    repas.sort(key=lambda x: (x["date"], x["heure_debut"]))

    total_couverts    = sum(r["couverts"] for r in repas if not r["estimation"])
    total_estimations = sum(r["couverts"] for r in repas if r["estimation"])

    context = {
        "repas":             repas,
        "total_couverts":    total_couverts,
        "total_estimations": total_estimations,
        "annee": annee, "mois": mois,
        "nom_mois": premier_jour.strftime("%B %Y").capitalize(),
        "mois_prec": mois_prec, "annee_prec": annee_prec,
        "mois_suiv": mois_suiv, "annee_suiv": annee_suiv,
        "today": today,
    }
    return render(request, "traiteur/planning.html", context)


# ── Réservation directe (traiteur) ────────────────────────────────────────────

@traiteur_required
def reserver(request):
    """Formulaire de réservation directe salle agapes — statut validée immédiatement."""
    form = TraiteurReservationDirecteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cd       = form.cleaned_data
        loge     = cd.get("loge")
        org      = cd.get("organisation") or ""
        date_r   = cd["date"]
        hd       = cd["heure_debut"]
        hf       = cd["heure_fin"]
        couverts = cd.get("nombre_repas") or 0
        note     = cd.get("commentaire") or ""
        salle    = cd["salle"]

        ReservationSalle.objects.create(
            loge=loge,
            salle=salle,
            date=date_r,
            heure_debut=hd,
            heure_fin=hf,
            statut="validee",
            nom_demandeur=loge.nom if loge else org,
            email_demandeur="traiteur@kellermann.local",
            organisation=loge.nom if loge else org,
            objet=note or "Agapes",
            nombre_participants=couverts,
            commentaire=note,
        )
        messages.success(request, f"Réservation créée et validée sur {salle.nom} le {date_r:%d/%m/%Y}.")
        return redirect("traiteur:planning")

    return render(request, "traiteur/reserver.html", {"form": form})


# ── Blocage de créneaux ───────────────────────────────────────────────────────

@traiteur_required
def bloquer(request):
    """Bloquer un créneau sur une ou plusieurs salles agapes."""
    form = BlocageCreneauxForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        blocage = form.save(commit=False)
        blocage.created_by = request.user
        blocage.save()
        form.save_m2m()
        messages.success(request, f"Créneau bloqué : {blocage.date} {blocage.heure_debut}–{blocage.heure_fin}.")
        return redirect("traiteur:calendrier")

    blocages = BlocageCreneaux.objects.filter(
        date__gte=date.today()
    ).prefetch_related("salles").order_by("date")

    return render(request, "traiteur/bloquer.html", {"form": form, "blocages": blocages})


@traiteur_required
def export_agapes_excel(request):
    """Export Excel agapes/banquets pour le traiteur — période et type filtrables."""
    from datetime import datetime as dt, date as date_type
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.http import HttpResponse

    today = date.today()
    annee_courante = today.year if today.month >= 9 else today.year - 1
    date_debut_s = request.GET.get('date_debut', '')
    date_fin_s   = request.GET.get('date_fin', '')
    type_export  = request.GET.get('type_export', 'tout')  # tout | agapes | banquet

    try:
        debut = dt.strptime(date_debut_s, '%Y-%m-%d').date() if date_debut_s else date_type(annee_courante, 9, 1)
        fin   = dt.strptime(date_fin_s,   '%Y-%m-%d').date() if date_fin_s   else date_type(annee_courante + 1, 6, 30)
    except ValueError:
        debut = date_type(annee_courante, 9, 1)
        fin   = date_type(annee_courante + 1, 6, 30)

    lignes = []
    if type_export in ('tout', 'agapes'):
        for r in Reservation.objects.filter(
            besoin_agapes=True, statut='validee', date__gte=debut, date__lte=fin
        ).select_related('loge', 'temple').order_by('date'):
            couverts = r.nombre_repas
            if not couverts and r.loge and r.loge.effectif_moyen_agapes:
                couverts = r.loge.effectif_moyen_agapes
            lignes.append((
                r.date.strftime('%d/%m/%Y'),
                r.loge.nom if r.loge else (r.nom_organisation or r.nom_demandeur),
                'Tenue + agapes',
                couverts,
                str(r.temple),
                f"{r.heure_debut:%H:%M} – {r.heure_fin:%H:%M}",
                r.commentaire,
            ))
    if type_export in ('tout', 'banquet'):
        for b in ReservationSalle.objects.filter(
            salle__type_salle='agapes', statut='validee', date__gte=debut, date__lte=fin
        ).select_related('salle').order_by('date'):
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

    # Excel
    wb  = openpyxl.Workbook()
    ws  = wb.active
    ws.title = f"Agapes {debut:%d/%m/%Y}-{fin:%d/%m/%Y}"
    hf    = Font(bold=True, color="C8A84B")
    hfill = PatternFill("solid", fgColor="0F2137")
    ctr   = Alignment(horizontal="center", vertical="center")
    thin  = Border(left=Side(style='thin'), right=Side(style='thin'),
                   top=Side(style='thin'), bottom=Side(style='thin'))
    headers = ["Date", "Loge / Organisation", "Type", "Couverts", "Lieu", "Horaires", "Commentaire"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = hf; cell.fill = hfill; cell.alignment = ctr; cell.border = thin
    for i, w in enumerate([14, 36, 20, 12, 22, 18, 40], 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    for row_idx, l in enumerate(lignes, 2):
        for col, val in enumerate(l, 1):
            c = ws.cell(row=row_idx, column=col, value=val)
            c.border = thin
            if col == 4:
                c.alignment = ctr

    # Total
    row_idx = len(lignes) + 3
    ws.cell(row=row_idx, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=row_idx, column=4, value=sum(l[3] or 0 for l in lignes)).font = Font(bold=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    fname = f"agapes_{debut:%d%m%Y}-{fin:%d%m%Y}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb.save(response)
    return response


@traiteur_required
def supprimer_blocage(request, pk):
    blocage = get_object_or_404(BlocageCreneaux, pk=pk)
    if request.method == "POST":
        blocage.delete()
        messages.success(request, "Blocage supprimé.")
    return redirect("traiteur:bloquer")


# ── Notification couverts (accessible aux membres) ────────────────────────────

@membre_ou_traiteur_required
def notification(request):
    """Formulaire permettant à un membre de notifier le traiteur d'un changement de couverts."""
    form = NotificationCouvertsForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        notif = NotificationCouverts.objects.create(
            loge=cd["loge"],
            date_tenue=cd["date_tenue"],
            nombre_couverts=cd["nombre_couverts"],
            commentaire=cd.get("commentaire") or "",
            email_contact=cd["email_contact"],
        )

        # Email au traiteur
        _envoyer_email_notification_traiteur(notif)
        # Email de confirmation au demandeur
        _envoyer_email_confirmation_demandeur(notif)

        messages.success(
            request,
            f"Votre notification a été transmise au traiteur. "
            f"Un email de confirmation a été envoyé à {notif.email_contact}."
        )
        return redirect("traiteur:notification_confirmee")

    return render(request, "traiteur/notification.html", {"form": form})


@membre_ou_traiteur_required
def notification_confirmee(request):
    return render(request, "traiteur/notification_confirmee.html")


# ── Emails notifications ──────────────────────────────────────────────────────

def _envoyer_email_notification_traiteur(notif):
    """Envoie un email au traiteur pour signaler la notification."""
    try:
        from temple_project.apps.administration.email_utils import (
            send_mail_kellermann, get_email_admin
        )
        sujet = f"[Traiteur] Notification couverts — {notif.loge} — {notif.date_tenue:%d/%m/%Y}"
        corps = (
            f"Une notification de couverts a été envoyée.\n\n"
            f"Loge       : {notif.loge}\n"
            f"Date tenue : {notif.date_tenue:%d/%m/%Y}\n"
            f"Couverts   : {notif.nombre_couverts}\n"
            f"Commentaire: {notif.commentaire or '—'}\n"
            f"Contact    : {notif.email_contact}\n"
        )
        send_mail_kellermann(sujet, corps, [get_email_admin()], fail_silently=True)
    except Exception:
        pass


def _envoyer_email_confirmation_demandeur(notif):
    """Envoie un email de confirmation au demandeur."""
    try:
        from temple_project.apps.administration.email_utils import send_mail_kellermann
        sujet = f"[Kellermann] Notification reçue — {notif.date_tenue:%d/%m/%Y}"
        corps = (
            f"Bonjour,\n\n"
            f"Votre notification a bien été transmise au traiteur.\n\n"
            f"Loge       : {notif.loge}\n"
            f"Date tenue : {notif.date_tenue:%d/%m/%Y}\n"
            f"Couverts   : {notif.nombre_couverts}\n"
            f"Commentaire: {notif.commentaire or '—'}\n\n"
            f"Cordialement,\nKellermann Réservations"
        )
        send_mail_kellermann(sujet, corps, [notif.email_contact], fail_silently=True)
    except Exception:
        pass
