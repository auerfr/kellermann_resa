import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin, get_email_traiteur
from django.db.models import Q, Sum
from .emails import envoyer_email_nouvelle_demande
from .models import (
    Reservation, ReservationSalle, SalleReunion, DemandeRegleRecurrence,
    RegleRecurrence, RegleRecurrenceSalle, DemandeRegleRecurrenceSalle,
    Temple, DemandeAccesPortail,
    ValidationSaison, ValidationSaisonLigne, MessageContact,
)
from temple_project.apps.loges.models import Loge
from .forms import DemandeReservationForm, DemandeReservationSalleForm, DemandeCabinetsForm, DemandeBanquetForm
from temple_project.apps.administration.journal import log_evenement


def soumettre_demande(request):
    if request.method == "POST":
        form = DemandeReservationForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            type_resa = cd.get('type_reservation') or 'exceptionnelle'

            if type_resa == 'congres':
                # Un congrès peut occuper plusieurs temples (+ salles de réunion).
                commun = dict(
                    loge=cd.get('loge'),
                    nom_organisation=cd.get('nom_organisation') or '',
                    type_reservation='congres',
                    sous_type=cd.get('sous_type') or 'standard',
                    statut='attente',
                    date=cd['date'], date_fin=cd.get('date_fin'),
                    heure_debut=cd['heure_debut'], heure_fin=cd['heure_fin'],
                    besoin_agapes=cd.get('besoin_agapes') or False,
                    nombre_repas=cd.get('nombre_repas') or 0,
                    besoin_micro=cd.get('besoin_micro') or False,
                    besoin_enceintes=cd.get('besoin_enceintes') or False,
                    profanes_admis=cd.get('profanes_admis') or False,
                    nom_demandeur=cd['nom_demandeur'],
                    email_demandeur=cd['email_demandeur'],
                    commentaire=cd.get('commentaire') or '',
                )
                premier = None
                for tp in cd['temples']:
                    r = Reservation.objects.create(temple=tp, **commun)
                    if premier is None:
                        premier = r
                if cd.get('cabinets'):
                    premier.cabinets.set(cd['cabinets'])
                org_nom = cd['loge'].nom if cd.get('loge') else (cd.get('nom_organisation') or '')
                for salle in cd.get('salles_reunion') or []:
                    ReservationSalle.objects.create(
                        loge=cd.get('loge'), salle=salle,
                        date=cd['date'], heure_debut=cd['heure_debut'], heure_fin=cd['heure_fin'],
                        statut='attente', nom_demandeur=cd['nom_demandeur'],
                        email_demandeur=cd['email_demandeur'], organisation=org_nom,
                        objet='Congrès', nombre_participants=cd.get('nombre_repas') or 1,
                        commentaire=cd.get('commentaire') or '',
                    )
                envoyer_email_nouvelle_demande(premier)
                lien = request.build_absolute_uri('/reservations/suivi/' + str(premier.uuid) + '/')
                temples_str = ', '.join(str(t) for t in cd['temples'])
                send_mail_kellermann(
                    subject="Confirmation de votre demande de congres",
                    message=f"""Votre demande de congres du {cd['date']} a bien ete recue.
Temples : {temples_str}
Reference : {premier.uuid}
Vous pouvez suivre votre demande sur : {lien}""",
                    recipient_list=[cd['email_demandeur']],
                )
                messages.success(request, "Votre demande de congres a ete soumise avec succes.")
                return redirect("reservations:confirmation", uuid=premier.uuid)

            # Tenue exceptionnelle : une seule réservation
            resa = form.save(commit=False)
            resa.type_reservation = "exceptionnelle"
            resa.statut = "attente"
            resa.save()
            form.save_m2m()
            envoyer_email_nouvelle_demande(resa)
            lien = request.build_absolute_uri('/reservations/suivi/' + str(resa.uuid) + '/')
            send_mail_kellermann(
                subject="Confirmation de votre demande de reservation",
                message=f"""Votre demande pour le {resa.date} a bien ete recue.
Reference : {resa.uuid}
Vous pouvez suivre votre demande sur : {lien}""",
                recipient_list=[resa.email_demandeur],
            )
            messages.success(request, "Votre demande a ete soumise avec succes.")
            return redirect("reservations:confirmation", uuid=resa.uuid)
    else:
        form = DemandeReservationForm()
    from temple_project.apps.administration.models import Parametres
    return render(request, "reservations/formulaire.html", {
        "form": form, "tarifs": Parametres.get_instance(),
    })


def soumettre_demande_salle(request):
    """Réservation publique d'une ou plusieurs salles de réunion (pas de token requis)."""
    import uuid as uuid_module
    from datetime import date as date_cls, time as time_cls

    # Salles proposées : réunion + agapes (pas les cabinets, pas les temples)
    salles_qs = SalleReunion.objects.filter(
        type_salle__in=['reunion', 'agapes'], actif=True
    ).order_by('type_salle', 'nom')
    salles_par_type = {}
    for s in salles_qs:
        salles_par_type.setdefault(s.get_type_salle_display(), []).append(s)

    loges = Loge.objects.filter(actif=True).order_by('nom')

    if request.method == "POST":
        salle_pks    = request.POST.getlist('salles')
        date_str     = request.POST.get('date', '').strip()
        hd_str       = request.POST.get('heure_debut', '').strip()
        hf_str       = request.POST.get('heure_fin', '').strip()
        nom_dem      = request.POST.get('nom_demandeur', '').strip()
        email_dem    = request.POST.get('email_demandeur', '').strip()
        loge_pk      = request.POST.get('loge_pk', '').strip()
        org_libre    = request.POST.get('organisation', '').strip()
        objet        = request.POST.get('objet', '').strip() or 'Réunion'
        participants = request.POST.get('nombre_participants', '1').strip()
        type_reunion = request.POST.get('type_reunion', 'reunion')
        commentaire  = request.POST.get('commentaire', '').strip()

        errors = []
        loge = None
        if loge_pk:
            try:
                loge = Loge.objects.get(pk=int(loge_pk))
            except (Loge.DoesNotExist, ValueError):
                pass
        organisation = loge.nom if loge else org_libre

        if not salle_pks:
            errors.append("Sélectionnez au moins une salle.")
        if not nom_dem:
            errors.append("Votre nom est requis.")
        if not email_dem:
            errors.append("Votre email est requis.")

        try:
            date_r = date_cls.fromisoformat(date_str)
        except (ValueError, TypeError):
            date_r = None
            errors.append("Date invalide.")
        try:
            hd = time_cls.fromisoformat(hd_str)
            hf = time_cls.fromisoformat(hf_str)
            if hf <= hd:
                errors.append("L'heure de fin doit être après l'heure de début.")
        except (ValueError, TypeError):
            hd = hf = None
            errors.append("Horaires invalides.")

        salles_sel = list(SalleReunion.objects.filter(pk__in=salle_pks, actif=True))
        conflits = []
        if not errors and date_r and hd and hf:
            for salle in salles_sel:
                occupe = ReservationSalle.objects.filter(
                    salle=salle, date=date_r,
                    heure_debut__lt=hf, heure_fin__gt=hd,
                    statut__in=['attente', 'validee'],
                ).exists()
                if occupe:
                    conflits.append(salle.nom)
            if conflits:
                errors.append(f"Conflit sur : {', '.join(conflits)}. Choisissez d'autres créneaux ou d'autres salles.")

        if not errors and salles_sel:
            try:
                nb_part = max(1, int(participants))
            except ValueError:
                nb_part = 1

            group_id = uuid_module.uuid4() if len(salles_sel) > 1 else None
            resas = []
            for salle in salles_sel:
                r = ReservationSalle.objects.create(
                    loge=loge,
                    salle=salle,
                    date=date_r,
                    heure_debut=hd,
                    heure_fin=hf,
                    statut='attente',
                    nom_demandeur=nom_dem,
                    email_demandeur=email_dem,
                    organisation=organisation,
                    objet=objet,
                    nombre_participants=nb_part,
                    type_reunion=type_reunion,
                    commentaire=commentaire,
                    group_uuid=group_id,
                )
                resas.append(r)

            noms_salles = ', '.join(s.nom for s in salles_sel)
            send_mail_kellermann(
                subject="[Kellermann] Confirmation de votre demande de salle",
                message=(
                    f"Bonjour {nom_dem},\n\n"
                    f"Votre demande de salle a bien été enregistrée.\n\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Date     : {date_r:%d/%m/%Y}\n"
                    f"Horaires : {hd_str} – {hf_str}\n"
                    f"Objet    : {objet}\n\n"
                    f"L'administration vous contactera après validation.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[email_dem],
            )
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande salle — {organisation or nom_dem}",
                message=(
                    f"Nouvelle demande de salle.\n\n"
                    f"Organisation : {organisation or nom_dem}\n"
                    f"Contact : {nom_dem} — {email_dem}\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Date : {date_r:%d/%m/%Y} {hd_str}–{hf_str}\n"
                    f"Type : {dict(ReservationSalle.TYPE_REUNION_CHOICES).get(type_reunion, type_reunion)}\n"
                ),
                recipient_list=[get_email_admin()],
            )
            messages.success(request, "Demande envoyée — vous recevrez une confirmation par email.")
            return redirect("reservations:confirmation_salle", uuid=resas[0].uuid)

        for err in errors:
            messages.error(request, err)

    return render(request, "reservations/formulaire_salle.html", {
        "loges":                loges,
        "salles_par_type":      salles_par_type,
        "type_reunion_choices": ReservationSalle.TYPE_REUNION_CHOICES,
    })


def confirmation(request, uuid):
    resa = get_object_or_404(Reservation, uuid=uuid)
    return render(request, "reservations/confirmation.html", {"reservation": resa})


def confirmation_salle(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    # Si multi-salles, récupérer toutes les réservations du groupe
    if resa.group_uuid:
        groupe = list(ReservationSalle.objects.filter(group_uuid=resa.group_uuid).select_related('salle').order_by('salle__nom'))
    else:
        groupe = [resa]
    return render(request, "reservations/confirmation_salle.html", {"reservation": resa, "groupe": groupe})


def suivi_reservation(request, uuid):
    resa = get_object_or_404(Reservation, uuid=uuid)
    return render(request, "reservations/suivi.html", {"reservation": resa})


def suivi_salle(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    return render(request, "reservations/suivi_salle.html", {"reservation": resa})


def demande_cabinets(request):
    _loges = Loge.objects.filter(actif=True).order_by('nom')
    _cabinets_ctx = lambda: {
        "loges": _loges,
        "cabinets_json": json.dumps(
            list(SalleReunion.objects.filter(
                type_salle='cabinet_reflexion', actif=True
            ).order_by('nom').values('pk', 'nom'))
        ),
    }
    if request.method == "POST":
        form = DemandeCabinetsForm(request.POST)
        if form.is_valid():
            # Vérifier la disponibilité des cabinets
            date = form.cleaned_data['date']
            heure_debut = form.cleaned_data['heure_debut']
            heure_fin = form.cleaned_data['heure_fin']
            nombre_cabinets_demandes = int(form.cleaned_data['nombre_cabinets'])

            # Compter les cabinets déjà réservés sur ce créneau
            reservations_existantes = ReservationSalle.objects.filter(
                salle__type_salle='cabinet_reflexion',
                date=date,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut,
                statut__in=['attente', 'validee']
            ).aggregate(
                total_cabinets=Sum('nombre_cabinets')
            )['total_cabinets'] or 0

            # Nombre total de cabinets disponibles
            total_cabinets_disponibles = SalleReunion.objects.filter(
                type_salle='cabinet_reflexion',
                actif=True
            ).count()

            cabinets_disponibles = total_cabinets_disponibles - reservations_existantes

            if cabinets_disponibles < nombre_cabinets_demandes:
                messages.error(
                    request,
                    f"Pas assez de cabinets disponibles. {cabinets_disponibles} cabinet(s) disponible(s), "
                    f"{nombre_cabinets_demandes} demandé(s)."
                )
                return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})

            # Récupérer la préférence de cabinet (optionnelle)
            cabinet_prefere_pk = request.POST.get('cabinet_prefere') or None
            cabinet_prefere_obj = None
            if cabinet_prefere_pk:
                try:
                    cabinet_prefere_obj = SalleReunion.objects.get(
                        pk=cabinet_prefere_pk, type_salle='cabinet_reflexion', actif=True
                    )
                except SalleReunion.DoesNotExist:
                    cabinet_prefere_obj = None

            # Construire la liste des cabinets libres en priorisant le cabinet préféré
            from django.db.models import Case, When, Value, IntegerField as DBIntegerField
            cabinets_libres_qs = SalleReunion.objects.filter(
                type_salle='cabinet_reflexion',
                actif=True,
            ).exclude(
                Q(reservations__date=date) &
                Q(reservations__heure_debut__lt=heure_fin) &
                Q(reservations__heure_fin__gt=heure_debut) &
                Q(reservations__statut__in=['attente', 'validee'])
            ).distinct()

            if cabinet_prefere_obj:
                cabinets_libres_qs = cabinets_libres_qs.annotate(
                    _prio=Case(
                        When(pk=cabinet_prefere_obj.pk, then=Value(0)),
                        default=Value(1),
                        output_field=DBIntegerField(),
                    )
                ).order_by('_prio', 'nom')

            cabinets_libres = list(cabinets_libres_qs[:nombre_cabinets_demandes])

            if len(cabinets_libres) < nombre_cabinets_demandes:
                messages.error(request, "Erreur interne : pas assez de cabinets libres trouvés.")
                return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})

            # Créer une réservation par cabinet
            reservations_creees = []
            for cabinet in cabinets_libres:
                resa = ReservationSalle.objects.create(
                    loge=form.cleaned_data.get('loge'),
                    salle=cabinet,
                    date=date,
                    heure_debut=heure_debut,
                    heure_fin=heure_fin,
                    statut="attente",
                    nom_demandeur=form.cleaned_data['nom_demandeur'],
                    email_demandeur=form.cleaned_data['email_demandeur'],
                    organisation=form.cleaned_data['organisation'],
                    objet=form.cleaned_data['objet'],
                    nombre_cabinets=1,
                    cabinet_prefere=cabinet_prefere_obj,
                    commentaire=form.cleaned_data['commentaire'],
                )
                reservations_creees.append(resa)

            # Envoyer un email de confirmation
            send_mail_kellermann(
                subject="Confirmation de votre demande de cabinets de réflexion",
                message=(
                    f"Votre demande de {nombre_cabinets_demandes} cabinet(s) de réflexion "
                    f"pour le {date} de {heure_debut} à {heure_fin} a bien été reçue.\n"
                    f"Référence(s) : {', '.join([str(r.uuid) for r in reservations_creees])}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(reservations_creees[0].uuid) + '/')}"
                ),
                recipient_list=[form.cleaned_data['email_demandeur']],
            )

            messages.success(request, f"Votre demande de {nombre_cabinets_demandes} cabinet(s) a été soumise avec succès.")
            return redirect("reservations:confirmation_salle", uuid=reservations_creees[0].uuid)
    else:
        form = DemandeCabinetsForm()

    return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})


def api_cabinets_disponibles(request):
    """API pour vérifier le nombre de cabinets disponibles sur un créneau"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        date = request.GET.get('date')
        heure_debut = request.GET.get('heure_debut')
        heure_fin = request.GET.get('heure_fin')

        if not all([date, heure_debut, heure_fin]):
            return JsonResponse({'error': 'Paramètres manquants'}, status=400)

        exclude_pk = request.GET.get('exclude_pk')

        cabinets = SalleReunion.objects.filter(
            type_salle='cabinet_reflexion', actif=True
        ).order_by('nom')

        result = []
        for cabinet in cabinets:
            qs = ReservationSalle.objects.filter(
                salle=cabinet,
                date=date,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut,
                statut__in=['attente', 'validee'],
            )
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            occupe = qs.exists()
            result.append({"pk": cabinet.pk, "nom": cabinet.nom, "libre": not occupe})

        disponibles = sum(1 for c in result if c["libre"])
        return JsonResponse({
            "total": len(result),
            "disponibles": disponibles,
            "cabinets": result,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def demande_banquet(request):
    salles_agapes = SalleReunion.objects.filter(
        type_salle='agapes', actif=True
    ).order_by('-capacite', 'nom')
    if not salles_agapes.exists():
        messages.error(request, "Aucune salle de banquet n'est disponible.")
        return redirect('reservations:demande')

    if request.method == "POST":
        form = DemandeBanquetForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            heure_debut = form.cleaned_data['heure_debut']
            heure_fin = form.cleaned_data['heure_fin']
            pref_pk = form.cleaned_data.get('salle_preference')

            salle_banquet = salles_agapes.filter(pk=pref_pk).first() or salles_agapes.first()

            # Verifier s'il y a deja une reservation sur ce creneau
            conflit = ReservationSalle.objects.filter(
                salle=salle_banquet,
                date=date,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut,
                statut__in=['attente', 'validee']
            ).exists()

            if conflit:
                messages.error(request, f"La salle « {salle_banquet.nom} » n'est pas disponible sur ce créneau.")
                return render(request, "reservations/formulaire_banquet.html", {"form": form})

            # Tout banquet d'ordre necessite une demande parallele au traiteur
            note_traiteur = (
                "[Banquet d'ordre — une demande doit être adressée en parallèle au "
                "traiteur pour confirmer sa capacité à assurer ce banquet.]"
            )
            nl = chr(10)
            commentaire_complet = (note_traiteur + nl + form.cleaned_data['commentaire']).strip()

            # Creer la reservation
            resa = ReservationSalle.objects.create(
                loge=form.cleaned_data.get('loge'),
                salle=salle_banquet,
                date=date,
                heure_debut=heure_debut,
                heure_fin=heure_fin,
                statut="attente",
                nom_demandeur=form.cleaned_data['nom_demandeur'],
                email_demandeur=form.cleaned_data['email_demandeur'],
                organisation=str(form.cleaned_data['loge']),
                objet="Banquet d'ordre",
                type_reunion="banquet",
                nombre_participants=form.cleaned_data['nombre_repas'],
                nombre_cabinets=1,
                commentaire=commentaire_complet,
            )

            # Envoyer un email de confirmation (demandeur + traiteur)
            destinataires = [form.cleaned_data['email_demandeur']]
            email_t = get_email_traiteur()
            if email_t:
                destinataires.append(email_t)
            message = (
                f"Votre demande de banquet d'ordre pour le {date:%d/%m/%Y} "
                f"de {heure_debut} à {heure_fin} a bien été reçue." + nl +
                f"Salle : {salle_banquet.nom}" + nl +
                f"Nombre de repas : {form.cleaned_data['nombre_repas']}" + nl + nl +
                "IMPORTANT : cette réservation de salle ne vaut pas accord du traiteur. "
                "Vous devez adresser en parallèle une demande au traiteur afin de "
                "vérifier sa capacité à assurer ce banquet d'ordre." + nl + nl +
                f"Référence : {resa.uuid}" + nl +
                "Vous pouvez suivre votre demande sur : "
                f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(resa.uuid) + '/')}"
            )
            send_mail_kellermann(
                subject="Confirmation de votre demande de banquet d'ordre",
                message=message,
                recipient_list=destinataires,
            )

            messages.success(request, "Votre demande de banquet d'ordre a été soumise avec succès.")
            return redirect("reservations:confirmation_banquet", uuid=resa.uuid)
    else:
        form = DemandeBanquetForm()

    return render(request, "reservations/formulaire_banquet.html", {"form": form})


def confirmation_banquet(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    return render(request, "reservations/confirmation_banquet.html", {"reservation": resa})


def _fmt_heure(t):
    return t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5]


def choisir_recurrence(request):
    """Page d'aiguillage : récurrence temple ou salle de réunion."""
    return render(request, 'reservations/choisir_recurrence.html')


def soumettre_demande_recurrence_salle_publique(request):
    """Formulaire public (sans token) pour demander une récurrence salle."""
    loges = Loge.objects.filter(actif=True).order_by('nom')
    salles_reunion = list(SalleReunion.objects.filter(
        type_salle__in=['reunion', 'agapes'], actif=True
    ).order_by('type_salle', 'nom'))
    salles_par_type = {}
    for s in salles_reunion:
        salles_par_type.setdefault(s.get_type_salle_display(), []).append(s)

    MOIS = [
        (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'Décembre'),
        (1,'Janvier'),(2,'Février'),(3,'Mars'),(4,'Avril'),(5,'Mai'),(6,'Juin'),
    ]

    if request.method == 'POST':
        loge_pk        = request.POST.get('loge_pk', '').strip()
        salle_pks      = request.POST.getlist('salles')
        jour_semaine   = request.POST.get('jour_semaine', '').strip()
        numero_semaine = request.POST.get('numero_semaine', '').strip()
        hd_str         = request.POST.get('heure_debut', '19:30').strip()
        hf_str         = request.POST.get('heure_fin', '22:30').strip()
        mois_actifs    = [int(m) for m in request.POST.getlist('mois_actifs') if m.isdigit()]
        objet          = request.POST.get('objet', '').strip() or 'Réunion'
        type_reunion   = request.POST.get('type_reunion', 'reunion')
        participants   = request.POST.get('nombre_participants', '0').strip()
        commentaire    = request.POST.get('commentaire', '').strip()
        nom_dem        = request.POST.get('nom_demandeur', '').strip()
        email_dem      = request.POST.get('email_demandeur', '').strip()

        errors = []
        loge = None
        if loge_pk:
            try:
                loge = Loge.objects.get(pk=int(loge_pk))
            except (Loge.DoesNotExist, ValueError):
                errors.append("Loge introuvable.")
        if not loge:
            errors.append("Sélectionnez une loge.")
        if not salle_pks:
            errors.append("Sélectionnez au moins une salle.")
        if not nom_dem:
            errors.append("Votre nom est requis.")
        if not email_dem:
            errors.append("Votre email est requis.")
        if not jour_semaine or not jour_semaine.lstrip('-').isdigit():
            errors.append("Précisez la fréquence (semaine et jour).")
        if not numero_semaine or not numero_semaine.lstrip('-').isdigit():
            errors.append("Précisez le numéro de semaine.")

        salles_sel = list(SalleReunion.objects.filter(pk__in=salle_pks, actif=True))

        if not errors and loge and salles_sel:
            try:
                nb_part = int(participants)
            except ValueError:
                nb_part = 0
            demande = DemandeRegleRecurrenceSalle.objects.create(
                loge=loge,
                jour_semaine=int(jour_semaine),
                numero_semaine=int(numero_semaine),
                heure_debut=hd_str,
                heure_fin=hf_str,
                mois_actifs=mois_actifs or [],
                objet=objet,
                type_reunion=type_reunion,
                nombre_participants=nb_part,
                nom_demandeur=nom_dem,
                email_demandeur=email_dem,
                commentaire=commentaire,
                statut='attente',
            )
            demande.salles.set(salles_sel)

            noms_salles = ', '.join(s.nom for s in salles_sel)
            send_mail_kellermann(
                subject="[Kellermann] Confirmation de votre demande de récurrence salle",
                message=(
                    f"Bonjour {nom_dem},\n\n"
                    f"Votre demande de règle de récurrence salle a bien été reçue.\n\n"
                    f"Loge     : {loge}\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires : {hd_str} – {hf_str}\n"
                    f"Objet    : {objet}\n\n"
                    f"L'administration vous contactera après validation.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[email_dem],
            )
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande récurrence salle — {loge}",
                message=(
                    f"Nouvelle demande de règle de récurrence salle.\n\n"
                    f"Loge     : {loge}\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires : {hd_str} – {hf_str}\n"
                    f"Type     : {dict(ReservationSalle.TYPE_REUNION_CHOICES).get(type_reunion, type_reunion)}\n"
                    f"Contact  : {nom_dem} — {email_dem}\n"
                ),
                recipient_list=[get_email_admin()],
            )
            messages.success(request, "Demande envoyée — vous recevrez une confirmation par email.")
            return redirect('reservations:confirmation_recurrence_salle', uuid=demande.uuid)

        for err in errors:
            messages.error(request, err)

    return render(request, 'reservations/formulaire_recurrence_salle.html', {
        'loges':                loges,
        'salles_par_type':      salles_par_type,
        'mois':                 MOIS,
        'type_reunion_choices': ReservationSalle.TYPE_REUNION_CHOICES,
        'jour_choices':         RegleRecurrenceSalle.JOUR_CHOICES,
        'semaine_choices':      RegleRecurrenceSalle.SEMAINE_CHOICES,
    })


def confirmation_recurrence_salle(request, uuid):
    demande = get_object_or_404(DemandeRegleRecurrenceSalle, uuid=uuid)
    return render(request, 'reservations/confirmation_recurrence_salle.html', {'demande': demande})


def soumettre_demande_recurrence(request):
    """Formulaire front-end : une loge demande une règle de récurrence."""
    HORAIRES_GROUPED = [
        ("Matin (06:00–12:00)", [
            ("06:00", "06h00"), ("06:30", "06h30"),
            ("07:00", "07h00"), ("07:30", "07h30"),
            ("08:00", "08h00"), ("08:30", "08h30"),
            ("09:00", "09h00"), ("09:30", "09h30"),
            ("10:00", "10h00"), ("10:30", "10h30"),
            ("11:00", "11h00"), ("11:30", "11h30"),
        ]),
        ("Après-midi (12:00–18:00)", [
            ("12:00", "12h00"), ("12:30", "12h30"),
            ("13:00", "13h00"), ("13:30", "13h30"),
            ("14:00", "14h00"), ("14:30", "14h30"),
            ("15:00", "15h00"), ("15:30", "15h30"),
            ("16:00", "16h00"), ("16:30", "16h30"),
            ("17:00", "17h00"), ("17:30", "17h30"),
        ]),
        ("Soir (18:00–23:30)", [
            ("18:00", "18h00"), ("18:30", "18h30"),
            ("19:00", "19h00"), ("19:30", "19h30"),
            ("20:00", "20h00"), ("20:30", "20h30"),
            ("21:00", "21h00"), ("21:30", "21h30"),
            ("22:00", "22h00"), ("22:30", "22h30"),
            ("23:00", "23h00"), ("23:30", "23h30"),
        ]),
    ]
    MOIS = [
        (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'Décembre'),
        (1,'Janvier'),(2,'Février'),(3,'Mars'),(4,'Avril'),(5,'Mai'),(6,'Juin'),
    ]
    TRANCHES = [
        ('Matin', '09:00', '12:00'),
        ('Après-midi', '14:00', '17:00'),
        ('Soir', '19:30', '22:30'),
        ('Journée complète', '09:00', '17:00'),
    ]

    if request.method == 'POST':
        try:
            mois_actifs = [int(m) for m in request.POST.getlist('mois_actifs') if m.isdigit()]
            demande = DemandeRegleRecurrence.objects.create(
                loge_id        = request.POST['loge'],
                temple_id      = request.POST['temple'],
                jour_semaine   = int(request.POST['jour_semaine']),
                numero_semaine = int(request.POST['numero_semaine']),
                heure_debut    = request.POST['heure_debut'],
                heure_fin      = request.POST['heure_fin'],
                mois_actifs    = mois_actifs,
                nom_demandeur  = request.POST['nom_demandeur'].strip(),
                email_demandeur= request.POST['email_demandeur'].strip(),
                commentaire    = request.POST.get('commentaire', '').strip(),
                statut         = 'attente',
            )
            # Email à l'admin
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande de règle – {demande.loge}",
                message=(
                    f"Nouvelle demande de règle de récurrence.\n\n"
                    f"Loge      : {demande.loge}\n"
                    f"Temple    : {demande.temple}\n"
                    f"Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires  : {_fmt_heure(demande.heure_debut)} – {_fmt_heure(demande.heure_fin)}\n"
                    f"Mois      : {', '.join(str(m) for m in demande.mois_actifs) or 'Tous'}\n"
                    f"Demandeur : {demande.nom_demandeur} ({demande.email_demandeur})\n"
                    f"Commentaire : {demande.commentaire}\n\n"
                    f"Connectez-vous pour valider ou refuser cette demande."
                ),
                recipient_list=[get_email_admin()],
            )
            # Email de confirmation au demandeur
            send_mail_kellermann(
                subject="[Kellermann] Confirmation de votre demande de récurrence",
                message=(
                    f"Bonjour {demande.nom_demandeur},\n\n"
                    f"Votre demande de règle de récurrence a bien été reçue.\n\n"
                    f"Récapitulatif :\n"
                    f"  Loge      : {demande.loge}\n"
                    f"  Temple    : {demande.temple}\n"
                    f"  Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"  Horaires  : {_fmt_heure(demande.heure_debut)} – {_fmt_heure(demande.heure_fin)}\n\n"
                    f"Référence : {demande.uuid}\n\n"
                    f"Vous serez informé(e) par email dès qu'elle sera traitée.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[demande.email_demandeur],
            )
            return redirect('reservations:confirmation_recurrence', uuid=demande.uuid)
        except Exception as e:
            messages.error(request, f"Erreur lors de la soumission : {e}")

    return render(request, 'reservations/formulaire_recurrence.html', {
        'loges'   : Loge.objects.filter(actif=True).order_by('nom'),
        'temples' : Temple.objects.all(),
        'jours'   : RegleRecurrence.JOUR_CHOICES,
        'semaines': RegleRecurrence.SEMAINE_CHOICES,
        'horaires': HORAIRES_GROUPED,
        'mois'    : MOIS,
        'tranches': TRANCHES,
    })


def confirmation_recurrence(request, uuid):
    demande = get_object_or_404(DemandeRegleRecurrence, uuid=uuid)
    return render(request, 'reservations/confirmation_recurrence.html', {'demande': demande})


def suivi_recurrence(request, uuid):
    demande = get_object_or_404(DemandeRegleRecurrence, uuid=uuid)
    return render(request, 'reservations/suivi_recurrence.html', {'demande': demande})


def api_verifier_conflit(request):
    """API pour vérifier les conflits de réservation en temps réel."""
    date = request.GET.get('date')
    heure_debut = request.GET.get('heure_debut')
    heure_fin = request.GET.get('heure_fin')
    temple = request.GET.get('temple')
    salle = request.GET.get('salle')

    if not all([date, heure_debut, heure_fin]) or not (temple or salle):
        return JsonResponse({'conflit': False, 'message': ''})

    chevauchement = Q(heure_debut__lt=heure_fin, heure_fin__gt=heure_debut)

    if temple:
        base_qs = Reservation.objects.filter(temple=temple, date=date).filter(chevauchement)
        validees = base_qs.filter(statut='validee').exists()
        en_attente = base_qs.filter(statut='attente').exists()
    else:
        base_qs = ReservationSalle.objects.filter(salle=salle, date=date).filter(chevauchement)
        validees = base_qs.filter(statut='validee').exists()
        en_attente = base_qs.filter(statut='attente').exists()

    if validees:
        return JsonResponse({
            'conflit': True,
            'niveau': 'erreur',
            'message': 'Ce créneau est déjà validé et occupé.',
        })
    if en_attente:
        return JsonResponse({
            'conflit': True,
            'niveau': 'avertissement',
            'message': 'Une demande est en cours de traitement pour ce créneau — priorité au premier demandeur.',
        })
    return JsonResponse({
        'conflit': False,
        'message': 'Ce créneau semble disponible.',
    })


def api_apercu_recurrence(request):
    """Aperçu en direct d'une règle de récurrence : génère les dates de la saison
    à venir et indique, pour chacune, si le temple est libre ou déjà occupé.
    Purement indicatif (aucune écriture), pour guider la loge au moment de la demande."""
    from datetime import date as _date, timedelta, datetime as _dt
    import calendar as _cal

    try:
        temple_id = int(request.GET.get('temple'))
        jour      = int(request.GET.get('jour_semaine'))
        num       = int(request.GET.get('numero_semaine'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'message': 'Complétez le temple, le jour et la semaine.'})

    def _parse_h(v, defaut):
        try:
            return _dt.strptime(v, '%H:%M').time()
        except (TypeError, ValueError):
            return _dt.strptime(defaut, '%H:%M').time()

    hd = _parse_h(request.GET.get('heure_debut'), '19:00')
    hf = _parse_h(request.GET.get('heure_fin'),   '22:30')

    mois = [int(m) for m in request.GET.getlist('mois_actifs') if m.isdigit()]
    if not mois:
        mois = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]

    temple = Temple.objects.filter(pk=temple_id).first()
    if not temple:
        return JsonResponse({'ok': False, 'message': 'Temple introuvable.'})

    today = _date.today()
    annee = today.year if today.month >= 7 else today.year - 1
    d1, d2 = _date(annee, 9, 1), _date(annee + 1, 6, 30)

    def _dates_du_mois(an, mo):
        ndays = _cal.monthrange(an, mo)[1]
        matching = [_date(an, mo, j) for j in range(1, ndays + 1)
                    if _date(an, mo, j).weekday() == jour]
        if num == 0:
            return matching
        if num == -1:
            return matching[-1:] if matching else []
        return [matching[num - 1]] if len(matching) >= num else []

    JF = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.']
    dates = []
    for mo in mois:
        if mo in (7, 8):
            continue
        an = annee if mo >= 9 else annee + 1
        for d in _dates_du_mois(an, mo):
            if d1 <= d <= d2:
                dates.append(d)
    dates = sorted(set(dates))

    try:
        from .models import Indisponibilite
    except ImportError:
        Indisponibilite = None

    chevauchement = Q(heure_debut__lt=hf, heure_fin__gt=hd)
    resultats, libres = [], 0
    for d in dates:
        conflit = Reservation.objects.filter(
            temple=temple, date=d, statut__in=['validee', 'attente'],
        ).filter(chevauchement).select_related('loge').first()
        indispo = False
        if not conflit and Indisponibilite is not None:
            indispo = Indisponibilite.objects.filter(
                temples=temple, date_debut__lte=d, date_fin__gte=d,
            ).exists()
        libre = not conflit and not indispo
        if libre:
            libres += 1
        if conflit:
            par = str(conflit.loge) if conflit.loge else ''
            motif = f"occupé par {par}" if par else 'créneau déjà réservé'
        elif indispo:
            motif = 'temple indisponible'
        else:
            motif = ''
        resultats.append({
            'date':  d.isoformat(),
            'label': f"{JF[d.weekday()]} {d.strftime('%d/%m/%Y')}",
            'libre': libre,
            'motif': motif,
        })

    total = len(resultats)
    return JsonResponse({
        'ok': True,
        'saison':  f"{annee}-{annee + 1}",
        'temple':  str(temple),
        'total':   total,
        'libres':  libres,
        'occupes': total - libres,
        'dates':   resultats,
    })


def api_grille_congres(request):
    """Grille de disponibilité d'un congrès (jours × temples) + salles, en JSON propre."""
    from datetime import date as _date, timedelta
    temples_ids = request.GET.getlist('temples')
    salles_ids  = request.GET.getlist('salles')
    hd = request.GET.get('heure_debut')
    hf = request.GET.get('heure_fin')
    try:
        d1 = _date.fromisoformat(request.GET.get('date_debut'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'date invalide'}, status=400)
    try:
        d2 = _date.fromisoformat(request.GET.get('date_fin')) if request.GET.get('date_fin') else d1
    except ValueError:
        d2 = d1
    if d2 < d1:
        d2 = d1
    if not all([hd, hf]) or not temples_ids:
        return JsonResponse({'error': 'parametres manquants'}, status=400)

    temples = list(Temple.objects.filter(pk__in=temples_ids).order_by('nom'))
    salles  = list(SalleReunion.objects.filter(pk__in=salles_ids, type_salle='reunion').order_by('nom'))

    jours = []
    cur = d1
    while cur <= d2:
        jours.append(cur)
        cur += timedelta(days=1)

    def occ_temple(tp, jour):
        return [str(r.loge or r.nom_organisation or r.nom_demandeur)
                for r in Reservation.objects.filter(
                    temple=tp, date=jour, heure_debut__lt=hf, heure_fin__gt=hd,
                    statut__in=['attente', 'validee']).select_related('loge')]

    def occ_salle(s, jour):
        return [str(r.organisation or (r.loge.nom if r.loge else r.nom_demandeur))
                for r in ReservationSalle.objects.filter(
                    salle=s, date=jour, heure_debut__lt=hf, heure_fin__gt=hd,
                    statut__in=['attente', 'validee']).select_related('loge')]

    data_jours, nb_conflits = [], 0
    for j in jours:
        cells = []
        for tp in temples:
            occ = occ_temple(tp, j)
            if occ:
                nb_conflits += 1
            cells.append({'libre': not occ, 'detail': ', '.join(occ)})
        data_jours.append({'date': j.strftime('%d/%m/%Y'), 'cells': cells})

    data_salles = []
    for s in salles:
        occ_days = [j.strftime('%d/%m') for j in jours if occ_salle(s, j)]
        data_salles.append({'nom': str(s), 'libre': not occ_days, 'detail': ', '.join(occ_days)})

    # Alternatives : temples non demandés, libres sur toute la période
    requested = set()
    for i in temples_ids:
        try:
            requested.add(int(i))
        except (TypeError, ValueError):
            pass
    alternatives = []
    for tp in Temple.objects.exclude(pk__in=requested).order_by('nom'):
        if all(not occ_temple(tp, j) for j in jours):
            alternatives.append({'id': tp.pk, 'nom': str(tp)})

    return JsonResponse({
        'temples': [str(t) for t in temples],
        'jours': data_jours,
        'salles': data_salles,
        'alternatives': alternatives,
        'nb_conflits': nb_conflits,
    })


# ── Portail loge ──────────────────────────────────────────────────────────────

def contact_portail(request):
    loges = Loge.objects.filter(actif=True).order_by('nom')

    if request.method == 'POST':
        onglet = request.POST.get('onglet', 'acces')

        if onglet == 'acces':
            loge_id        = request.POST.get('loge') or None
            nom_loge_libre = request.POST.get('nom_loge_libre', '').strip()
            nom_venerable  = request.POST.get('nom_venerable', '').strip()
            email          = request.POST.get('email', '').strip()
            message        = request.POST.get('message', '').strip()

            if not nom_venerable or not email:
                messages.error(request, "Le nom du Vénérable et l'email sont obligatoires.")
                return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})

            loge_obj = None
            if loge_id:
                try:
                    loge_obj = Loge.objects.get(pk=loge_id)
                except Loge.DoesNotExist:
                    pass

            if not loge_obj and not nom_loge_libre:
                messages.error(request, "Veuillez sélectionner une loge ou saisir son nom.")
                return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})

            demande = DemandeAccesPortail.objects.create(
                loge=loge_obj,
                nom_loge_libre=nom_loge_libre if not loge_obj else '',
                nom_venerable=nom_venerable,
                email=email,
                message=message,
            )

            # Email à l'admin
            nom_loge_display = loge_obj.nom if loge_obj else nom_loge_libre
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande d'accès portail – {nom_loge_display}",
                message=(
                    f"Nouvelle demande d'accès au portail loge.\n\n"
                    f"Loge        : {nom_loge_display}\n"
                    f"Vénérable   : {nom_venerable}\n"
                    f"Email       : {email}\n"
                    f"Message     : {message or '(aucun)'}\n\n"
                    f"À valider dans le tableau de bord d'administration."
                ),
                recipient_list=[get_email_admin()],
            )

            return redirect('reservations:confirmation_contact')

        else:  # onglet == 'message'
            nom     = request.POST.get('nom', '').strip()
            email   = request.POST.get('email_message', '').strip()
            sujet   = request.POST.get('sujet', '').strip()
            message = request.POST.get('message_libre', '').strip()

            if not nom or not email or not message:
                messages.error(request, "Nom, email et message sont obligatoires.")
                return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'message'})

            # Enregistre le message (consultable + répondable dans la messagerie admin)
            MessageContact.objects.create(nom=nom, email=email, sujet=sujet, message=message)

            # Notification à l'admin
            send_mail_kellermann(
                subject=f"[Kellermann] Nouveau message – {sujet or nom}",
                message=(
                    f"Nouveau message reçu via le formulaire de contact.\n\n"
                    f"Nom    : {nom}\n"
                    f"Email  : {email}\n"
                    f"Sujet  : {sujet or '(non précisé)'}\n\n"
                    f"Message :\n{message}\n\n"
                    f"À consulter et répondre dans la messagerie de l'administration."
                ),
                recipient_list=[get_email_admin()],
            )
            return redirect('reservations:confirmation_contact')

    onglet = 'acces' if request.GET.get('onglet') == 'acces' else 'message'
    return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': onglet})


def confirmation_contact(request):
    return render(request, 'reservations/confirmation_contact.html')


def portail_loge(request, token):
    from datetime import date as date_cls
    from django.utils import timezone
    from temple_project.apps.administration.models import Parametres

    demande = get_object_or_404(DemandeAccesPortail, token=token, statut='validee')
    today   = date_cls.today()
    loge    = demande.loge

    # ── Mise à jour des informations de la loge par la loge elle-même ──────────
    if request.method == 'POST' and request.POST.get('action') == 'modifier_infos':
        if not loge:
            messages.error(request, "Aucune loge n'est associée à ce portail.")
            return redirect('reservations:portail_loge', token=token)
        loge.nom_contact    = request.POST.get('nom_contact', '').strip()
        loge.email          = request.POST.get('email', '').strip()
        loge.telephone      = request.POST.get('telephone', '').strip()
        loge.rite_precision = request.POST.get('rite_precision', '').strip()
        rite = request.POST.get('rite', '')
        if rite in dict(Loge.RITE_CHOICES):
            loge.rite = rite
        try:
            loge.effectif_total        = int(request.POST.get('effectif_total') or 0)
            loge.effectif_moyen_agapes = int(request.POST.get('effectif_moyen_agapes') or 0)
        except (ValueError, TypeError):
            messages.error(request, "Les effectifs doivent être des nombres entiers.")
            return redirect('reservations:portail_loge', token=token)
        loge.save()
        messages.success(request, "Les informations de votre loge ont bien été mises à jour.")
        return redirect('reservations:portail_loge', token=token)

    # ── Saison courante (par défaut) ─────────────────────────────────────────
    # De juillet à décembre on pointe sur la saison à venir (sept→juin) pour que
    # les loges voient leurs réservations de la prochaine saison sans changer de
    # sélecteur ; de janvier à juin, sur la saison en cours.
    annee_courante = today.year if today.month >= 7 else today.year - 1

    # ── Saison sélectionnée (GET ?saison=, sinon courante) ───────────────────
    try:
        annee_saison = int(request.GET.get('saison', annee_courante))
    except (ValueError, TypeError):
        annee_saison = annee_courante

    # Les 3 options proposées dans le sélecteur
    saisons_disponibles = [annee_courante - 1, annee_courante, annee_courante + 1]

    debut_saison = date_cls(annee_saison, 9, 1)
    fin_saison   = date_cls(annee_saison + 1, 6, 30)

    # ── Réservations temple : saison complète sélectionnée, validée ou en attente ───
    reservations_temple = Reservation.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut__in=['validee', 'attente'],
    ).select_related('temple').order_by('date') if loge else Reservation.objects.none()

    # Réservations salle (cabinets, banquet, réunion) liées à la loge
    reservations_salle_qs = ReservationSalle.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut__in=['validee', 'attente'],
    ).select_related('salle').order_by('date') if loge else ReservationSalle.objects.none()

    # Normalisation en dicts uniformes pour le template
    TYPE_SALLE_LABELS = {
        'agapes': 'Agapes', 'reunion': 'Salle de réunion',
        'cabinet_reflexion': 'Cabinet de réflexion',
    }

    def _temple_dict(r):
        return {
            'date': r.date, 'heure_debut': r.heure_debut, 'heure_fin': r.heure_fin,
            'statut': r.statut, 'get_statut_display': r.get_statut_display(),
            'type_code': 'temple', 'type_label': 'Temple',
            'type_resa': r.get_type_reservation_display(),
            'type_resa_code': r.type_reservation,
            'sous_type': r.get_sous_type_display() if r.sous_type and r.sous_type != 'standard' else '',
            'lieu': str(r.temple) if r.temple else '–',
            'detail': r.get_sous_type_display() if hasattr(r, 'sous_type') and r.sous_type else '',
            'obj': r,
        }

    def _salle_dict(r):
        ts = r.salle.type_salle if r.salle else ''
        return {
            'date': r.date, 'heure_debut': r.heure_debut, 'heure_fin': r.heure_fin,
            'statut': r.statut, 'get_statut_display': r.get_statut_display(),
            'type_code': ts, 'type_label': TYPE_SALLE_LABELS.get(ts, ts),
            'lieu': str(r.salle) if r.salle else '–',
            'detail': r.objet or '',
            'obj': r,
        }

    from itertools import chain
    tous_evenements = sorted(
        chain(
            (_temple_dict(r) for r in reservations_temple),
            (_salle_dict(r) for r in reservations_salle_qs),
        ),
        key=lambda d: d['date'],
    )

    evenements_passes = [d for d in tous_evenements if d['date'] < today]
    evenements_futurs = [d for d in tous_evenements if d['date'] >= today]

    # Encarts (temple uniquement pour prochaine tenue / nb restantes)
    prochaine_tenue  = reservations_temple.filter(date__gte=today, statut='validee').first()
    nb_restantes     = reservations_temple.filter(date__gte=today, statut='validee').count()

    # Conserver aussi les querysets bruts pour compatibilité template existante
    reservations         = reservations_temple
    reservations_passees = reservations_temple.filter(date__lt=today)
    reservations_futures = reservations_temple.filter(date__gte=today)

    # ── Validation de saison ─────────────────────────────────────────────────
    # La validation est indépendante du sélecteur de saison : on cherche
    # toute validation ouverte/soumise pour la loge, sans toucher à annee_saison.
    validation = None
    if loge:
        validation = ValidationSaison.objects.filter(
            loge=loge,
            statut__in=['ouverte', 'soumise'],
        ).prefetch_related('lignes').order_by('-annee').first()

    if request.method == 'POST' and request.POST.get('action') == 'soumettre_validation':
        if not loge or not validation or validation.statut != 'ouverte':
            messages.error(request, "Aucune validation ouverte pour votre loge.")
            return redirect('reservations:portail_loge', token=token)

        commentaire_global = request.POST.get('commentaire_global', '').strip()

        for ligne in validation.lignes.all():
            avis        = request.POST.get(f'avis_{ligne.pk}', 'ok')
            commentaire = request.POST.get(f'commentaire_{ligne.pk}', '').strip()
            if avis not in ('ok', 'deplacer', 'annuler'):
                avis = 'ok'
            ligne.avis        = avis
            ligne.commentaire = commentaire
            ligne.save()

        validation.commentaire_loge = commentaire_global
        validation.statut           = 'soumise'
        validation.date_reponse     = timezone.now()
        validation.save()

        nb_ok       = validation.lignes.filter(avis='ok').count()
        nb_deplacer = validation.lignes.filter(avis='deplacer').count()
        nb_annuler  = validation.lignes.filter(avis='annuler').count()

        # Email de confirmation à la loge
        if loge.email:
            send_mail_kellermann(
                subject=f"Votre validation de saison {annee_saison}-{annee_saison + 1} a bien été enregistrée",
                message=(
                    f"Bonjour,\n\n"
                    f"Votre validation du calendrier pour la saison "
                    f"{annee_saison}-{annee_saison + 1} a bien été reçue.\n\n"
                    f"Récapitulatif :\n"
                    f"  - {nb_ok} tenue(s) confirmée(s)\n"
                    f"  - {nb_deplacer} tenue(s) a deplacer\n"
                    f"  - {nb_annuler} tenue(s) a annuler\n"
                    + (f"\nVotre commentaire : {commentaire_global}\n" if commentaire_global else "")
                    + f"\nMerci pour votre retour.\n\nBien fraternellement,\nLes Temples Kellermann"
                ),
                recipient_list=[loge.email],
            )

        # Notification admin
        email_admin = get_email_admin()
        if email_admin:
            send_mail_kellermann(
                subject=f"[Validation saison] {loge.nom} a soumis sa reponse",
                message=(
                    f"{loge.nom} a valide son calendrier pour la saison "
                    f"{annee_saison}-{annee_saison + 1}.\n\n"
                    f"  - confirmees : {nb_ok}\n"
                    f"  - a deplacer : {nb_deplacer}\n"
                    f"  - a annuler  : {nb_annuler}\n"
                    + (f"\nCommentaire loge : {commentaire_global}" if commentaire_global else "")
                ),
                recipient_list=[email_admin],
            )

        messages.success(request, "Votre validation a bien été enregistrée. Merci !")
        log_evenement('soumission_validation_loge',
            f"Validation saison soumise : {loge.nom} – saison {annee_saison}-{annee_saison + 1} "
            f"({nb_ok} ok, {nb_deplacer} à déplacer, {nb_annuler} à annuler)",
            request=request, objet=validation)
        return redirect('reservations:portail_loge', token=token)

    return render(request, 'reservations/portail_loge.html', {
        'demande':               demande,
        'reservations':          reservations,
        'reservations_passees':  reservations_passees,
        'reservations_futures':  reservations_futures,
        'evenements_passes':     evenements_passes,
        'evenements_futurs':     evenements_futurs,
        'prochaine_tenue':       prochaine_tenue,
        'nb_restantes':          nb_restantes,
        'loge':                  loge,
        'validation':            validation,
        'annee_saison':          annee_saison,
        'annee_courante':        annee_courante,
        'saisons_disponibles':   saisons_disponibles,
        'today':                 today,
        'rites':                 Loge.RITE_CHOICES,
        'tarifs':                Parametres.get_instance(),
    })


# ── Portail loge : demande de salle (multi-salles + type réunion) ─────────────

def portail_demande_salle(request, token):
    """Depuis le portail loge, une loge demande une ou plusieurs salles de réunion."""
    import uuid as uuid_module
    from datetime import date as date_cls, time as time_cls

    demande_acces = get_object_or_404(DemandeAccesPortail, token=token, statut='validee')
    loge = demande_acces.loge

    salles_reunion = list(SalleReunion.objects.filter(
        type_salle__in=['reunion', 'agapes'], actif=True
    ).order_by('type_salle', 'nom'))
    salles_par_type = {}
    for s in salles_reunion:
        salles_par_type.setdefault(s.get_type_salle_display(), []).append(s)

    HORAIRES = [
        ("Matin",      [("08:00","08h00"),("09:00","09h00"),("10:00","10h00"),("11:00","11h00")]),
        ("Après-midi", [("14:00","14h00"),("15:00","15h00"),("16:00","16h00"),("17:00","17h00")]),
        ("Soir",       [("18:00","18h00"),("18:30","18h30"),("19:00","19h00"),("19:30","19h30"),
                        ("20:00","20h00"),("21:00","21h00"),("22:00","22h00"),("22:30","22h30")]),
    ]

    if request.method == 'POST':
        salle_pks     = request.POST.getlist('salles')
        date_str      = request.POST.get('date', '').strip()
        hd_str        = request.POST.get('heure_debut', '').strip()
        hf_str        = request.POST.get('heure_fin', '').strip()
        objet         = request.POST.get('objet', '').strip()
        type_reunion  = request.POST.get('type_reunion', 'reunion')
        participants  = request.POST.get('nombre_participants', '1').strip()
        commentaire   = request.POST.get('commentaire', '').strip()
        nom_dem       = (loge.nom_contact if loge else '').strip() or demande_acces.nom_venerable
        email_dem     = (loge.email if loge else '').strip() or ''

        errors = []
        if not salle_pks:
            errors.append("Sélectionnez au moins une salle.")
        try:
            date_r = date_cls.fromisoformat(date_str)
            if date_r < date_cls.today():
                errors.append("La date ne peut pas être dans le passé.")
        except (ValueError, TypeError):
            date_r = None
            errors.append("Date invalide.")
        try:
            hd = time_cls.fromisoformat(hd_str)
            hf = time_cls.fromisoformat(hf_str)
            if hf <= hd:
                errors.append("L'heure de fin doit être après l'heure de début.")
        except (ValueError, TypeError):
            hd = hf = None
            errors.append("Horaires invalides.")
        if not objet:
            errors.append("L'objet de la réunion est obligatoire.")
        if not email_dem:
            errors.append("Email de contact manquant — mettez à jour les infos de la loge.")

        salles_sel = list(SalleReunion.objects.filter(pk__in=salle_pks, actif=True))

        if not errors and date_r and hd and hf and salles_sel:
            try:
                nb_part = int(participants)
            except ValueError:
                nb_part = 1
            nom = loge.nom if loge else demande_acces.nom_venerable
            group_id = uuid_module.uuid4()
            created = []
            for salle in salles_sel:
                rs = ReservationSalle.objects.create(
                    loge=loge, salle=salle, date=date_r,
                    heure_debut=hd, heure_fin=hf, statut='attente',
                    nom_demandeur=nom_dem,
                    email_demandeur=email_dem,
                    organisation=nom,
                    objet=objet,
                    type_reunion=type_reunion,
                    nombre_participants=nb_part,
                    commentaire=commentaire,
                    group_uuid=group_id,
                )
                created.append(rs)

            # Email confirmation au demandeur
            noms_salles = ', '.join(s.nom for s in salles_sel)
            send_mail_kellermann(
                subject=f"[Kellermann] Confirmation de votre demande de salle — {date_r:%d/%m/%Y}",
                message=(
                    f"Bonjour {nom_dem},\n\n"
                    f"Votre demande de salle a bien été reçue.\n\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Date     : {date_r:%d/%m/%Y}\n"
                    f"Horaires : {hd:%H:%M} – {hf:%H:%M}\n"
                    f"Objet    : {objet}\n\n"
                    f"Vous serez notifié(e) par email à la validation.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[email_dem],
            )
            # Email à l'admin
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande de salle — {loge or nom} — {date_r:%d/%m/%Y}",
                message=(
                    f"Nouvelle demande de salle depuis le portail loge.\n\n"
                    f"Loge     : {loge or nom}\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Date     : {date_r:%d/%m/%Y}\n"
                    f"Horaires : {hd:%H:%M} – {hf:%H:%M}\n"
                    f"Type     : {dict(ReservationSalle.TYPE_REUNION_CHOICES).get(type_reunion, type_reunion)}\n"
                    f"Objet    : {objet}\n"
                    f"Contact  : {nom_dem} — {email_dem}\n"
                ),
                recipient_list=[get_email_admin()],
            )
            messages.success(request, f"Demande de salle envoyée pour le {date_r:%d/%m/%Y}.")
            return redirect('reservations:portail_loge', token=token)

        for err in errors:
            messages.error(request, err)

    return render(request, 'reservations/portail_demande_salle.html', {
        'demande_acces':  demande_acces,
        'loge':           loge,
        'salles_par_type': salles_par_type,
        'horaires':        HORAIRES,
        'type_reunion_choices': ReservationSalle.TYPE_REUNION_CHOICES,
        'token':           token,
    })


# ── Portail loge : demande de règle de récurrence salle ──────────────────────

def portail_demande_recurrence_salle(request, token):
    """Depuis le portail loge, demande d'une règle de récurrence sur des salles."""
    demande_acces = get_object_or_404(DemandeAccesPortail, token=token, statut='validee')
    loge = demande_acces.loge

    salles_reunion = list(SalleReunion.objects.filter(
        type_salle__in=['reunion', 'agapes'], actif=True
    ).order_by('type_salle', 'nom'))
    salles_par_type = {}
    for s in salles_reunion:
        salles_par_type.setdefault(s.get_type_salle_display(), []).append(s)

    MOIS = [
        (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'Décembre'),
        (1,'Janvier'),(2,'Février'),(3,'Mars'),(4,'Avril'),(5,'Mai'),(6,'Juin'),
    ]

    if request.method == 'POST':
        salle_pks      = request.POST.getlist('salles')
        jour_semaine   = request.POST.get('jour_semaine', '').strip()
        numero_semaine = request.POST.get('numero_semaine', '').strip()
        hd_str         = request.POST.get('heure_debut', '19:30').strip()
        hf_str         = request.POST.get('heure_fin', '22:30').strip()
        mois_actifs    = [int(m) for m in request.POST.getlist('mois_actifs') if m.isdigit()]
        objet          = request.POST.get('objet', '').strip() or 'Réunion'
        type_reunion   = request.POST.get('type_reunion', 'reunion')
        participants   = request.POST.get('nombre_participants', '0').strip()
        commentaire    = request.POST.get('commentaire', '').strip()
        nom_dem        = (loge.nom_contact if loge else '').strip() or demande_acces.nom_venerable
        email_dem      = (loge.email if loge else '').strip() or ''

        errors = []
        if not loge:
            errors.append("Aucune loge n'est associée à ce portail.")
        if not salle_pks:
            errors.append("Sélectionnez au moins une salle.")
        if not jour_semaine or not jour_semaine.lstrip('-').isdigit():
            errors.append("Jour de la semaine manquant.")
        if not numero_semaine or not numero_semaine.lstrip('-').isdigit():
            errors.append("Numéro de semaine manquant.")
        if not email_dem:
            errors.append("Email de contact manquant — mettez à jour les infos de la loge.")

        salles_sel = list(SalleReunion.objects.filter(pk__in=salle_pks, actif=True))

        if not errors and loge and salles_sel:
            try:
                nb_part = int(participants)
            except ValueError:
                nb_part = 0
            demande = DemandeRegleRecurrenceSalle.objects.create(
                loge=loge,
                jour_semaine=int(jour_semaine),
                numero_semaine=int(numero_semaine),
                heure_debut=hd_str,
                heure_fin=hf_str,
                mois_actifs=mois_actifs or [],
                objet=objet,
                type_reunion=type_reunion,
                nombre_participants=nb_part,
                nom_demandeur=nom_dem,
                email_demandeur=email_dem,
                commentaire=commentaire,
                statut='attente',
            )
            demande.salles.set(salles_sel)

            noms_salles = ', '.join(s.nom for s in salles_sel)
            # Email confirmation
            send_mail_kellermann(
                subject="[Kellermann] Confirmation de votre demande de récurrence salle",
                message=(
                    f"Bonjour {nom_dem},\n\n"
                    f"Votre demande de règle de récurrence salle a bien été reçue.\n\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires : {hd_str} – {hf_str}\n"
                    f"Objet    : {objet}\n\n"
                    f"L'administration vous contactera après validation.\n\n"
                    f"Fraternellement,\nL'administration des Temples Kellermann"
                ),
                recipient_list=[email_dem],
            )
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande récurrence salle — {loge}",
                message=(
                    f"Nouvelle demande de règle de récurrence salle.\n\n"
                    f"Loge     : {loge}\n"
                    f"Salle(s) : {noms_salles}\n"
                    f"Fréquence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires : {hd_str} – {hf_str}\n"
                    f"Type     : {dict(ReservationSalle.TYPE_REUNION_CHOICES).get(type_reunion, type_reunion)}\n"
                    f"Objet    : {objet}\n"
                    f"Contact  : {nom_dem} — {email_dem}\n"
                ),
                recipient_list=[get_email_admin()],
            )
            messages.success(request, "Demande de récurrence salle envoyée — l'administration vous contactera.")
            return redirect('reservations:portail_loge', token=token)

        for err in errors:
            messages.error(request, err)

    return render(request, 'reservations/portail_demande_recurrence_salle.html', {
        'demande_acces':  demande_acces,
        'loge':           loge,
        'salles_par_type': salles_par_type,
        'mois':            MOIS,
        'type_reunion_choices': ReservationSalle.TYPE_REUNION_CHOICES,
        'jour_choices':    RegleRecurrenceSalle.JOUR_CHOICES,
        'semaine_choices': RegleRecurrenceSalle.SEMAINE_CHOICES,
        'token':           token,
    })
