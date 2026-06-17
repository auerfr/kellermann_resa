import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin, get_email_traiteur
from django.db.models import Q, Sum
from .emails import envoyer_email_nouvelle_demande
from .models import (
    Reservation, ReservationSalle, SalleReunion, DemandeRegleRecurrence,
    RegleRecurrence, Temple, DemandeAccesPortail,
    ValidationSaison, ValidationSaisonLigne,
)
from temple_project.apps.loges.models import Loge
from .forms import DemandeReservationForm, DemandeReservationSalleForm, DemandeCabinetsForm, DemandeBanquetForm
from temple_project.apps.administration.journal import log_evenement


def soumettre_demande(request):
    if request.method == "POST":
        form = DemandeReservationForm(request.POST)
        if form.is_valid():
            resa = form.save(commit=False)
            if resa.type_reservation not in ('exceptionnelle', 'congres'):
                resa.type_reservation = "exceptionnelle"
            resa.statut = "attente"
            resa.save()
            form.save_m2m()
            envoyer_email_nouvelle_demande(resa)
            send_mail_kellermann(
                subject="Confirmation de votre demande de reservation",
                message=(
                    f"Votre demande pour le {resa.date} a bien ete recue.\n"
                    f"Reference : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi/' + str(resa.uuid) + '/')}"
                ),
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
    salles_reunion = SalleReunion.objects.filter(type_salle='reunion', actif=True)
    if request.method == "POST":
        form = DemandeReservationSalleForm(request.POST)
        form.fields['salle'].queryset = salles_reunion
        if form.is_valid():
            resa = form.save(commit=False)
            resa.statut = "attente"
            resa.save()
            send_mail_kellermann(
                subject="Confirmation de votre demande de salle",
                message=(
                    f"Votre demande de salle pour le {resa.date} a bien ete recue.\n"
                    f"Salle : {resa.salle}\n"
                    f"Reference : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(resa.uuid) + '/')}"
                ),
                recipient_list=[resa.email_demandeur],
            )
            messages.success(request, "Votre demande de salle a ete soumise avec succes.")
            return redirect("reservations:confirmation_salle", uuid=resa.uuid)
    else:
        form = DemandeReservationSalleForm()
        form.fields['salle'].queryset = salles_reunion
    loges = Loge.objects.filter(actif=True).order_by('nom')
    return render(request, "reservations/formulaire_salle.html", {"form": form, "loges": loges})


def confirmation(request, uuid):
    resa = get_object_or_404(Reservation, uuid=uuid)
    return render(request, "reservations/confirmation.html", {"reservation": resa})


def confirmation_salle(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    return render(request, "reservations/confirmation_salle.html", {"reservation": resa})


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
            # VÃ©rifier la disponibilitÃ© des cabinets
            date = form.cleaned_data['date']
            heure_debut = form.cleaned_data['heure_debut']
            heure_fin = form.cleaned_data['heure_fin']
            nombre_cabinets_demandes = int(form.cleaned_data['nombre_cabinets'])

            # Compter les cabinets dÃ©jÃ  rÃ©servÃ©s sur ce crÃ©neau
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
                    f"{nombre_cabinets_demandes} demandÃ©(s)."
                )
                return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})

            # RÃ©cupÃ©rer la prÃ©fÃ©rence de cabinet (optionnelle)
            cabinet_prefere_pk = request.POST.get('cabinet_prefere') or None
            cabinet_prefere_obj = None
            if cabinet_prefere_pk:
                try:
                    cabinet_prefere_obj = SalleReunion.objects.get(
                        pk=cabinet_prefere_pk, type_salle='cabinet_reflexion', actif=True
                    )
                except SalleReunion.DoesNotExist:
                    cabinet_prefere_obj = None

            # Construire la liste des cabinets libres en priorisant le cabinet prÃ©fÃ©rÃ©
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
                messages.error(request, "Erreur interne : pas assez de cabinets libres trouvÃ©s.")
                return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})

            # CrÃ©er une rÃ©servation par cabinet
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
                subject="Confirmation de votre demande de cabinets de rÃ©flexion",
                message=(
                    f"Votre demande de {nombre_cabinets_demandes} cabinet(s) de rÃ©flexion "
                    f"pour le {date} de {heure_debut} Ã  {heure_fin} a bien Ã©tÃ© reÃ§ue.\n"
                    f"RÃ©fÃ©rence(s) : {', '.join([str(r.uuid) for r in reservations_creees])}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(reservations_creees[0].uuid) + '/')}"
                ),
                recipient_list=[form.cleaned_data['email_demandeur']],
            )

            messages.success(request, f"Votre demande de {nombre_cabinets_demandes} cabinet(s) a Ã©tÃ© soumise avec succÃ¨s.")
            return redirect("reservations:confirmation_salle", uuid=reservations_creees[0].uuid)
    else:
        form = DemandeCabinetsForm()

    return render(request, "reservations/formulaire_cabinets.html", {"form": form, **_cabinets_ctx()})


def api_cabinets_disponibles(request):
    """API pour vÃ©rifier le nombre de cabinets disponibles sur un crÃ©neau"""
    if request.method != 'GET':
        return JsonResponse({'error': 'MÃ©thode non autorisÃ©e'}, status=405)

    try:
        date = request.GET.get('date')
        heure_debut = request.GET.get('heure_debut')
        heure_fin = request.GET.get('heure_fin')

        if not all([date, heure_debut, heure_fin]):
            return JsonResponse({'error': 'ParamÃ¨tres manquants'}, status=400)

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


def soumettre_demande_recurrence(request):
    """Formulaire front-end : une loge demande une rÃ¨gle de rÃ©currence."""
    HORAIRES_GROUPED = [
        ("Matin (06:00â€“12:00)", [
            ("06:00", "06h00"), ("06:30", "06h30"),
            ("07:00", "07h00"), ("07:30", "07h30"),
            ("08:00", "08h00"), ("08:30", "08h30"),
            ("09:00", "09h00"), ("09:30", "09h30"),
            ("10:00", "10h00"), ("10:30", "10h30"),
            ("11:00", "11h00"), ("11:30", "11h30"),
        ]),
        ("AprÃ¨s-midi (12:00â€“18:00)", [
            ("12:00", "12h00"), ("12:30", "12h30"),
            ("13:00", "13h00"), ("13:30", "13h30"),
            ("14:00", "14h00"), ("14:30", "14h30"),
            ("15:00", "15h00"), ("15:30", "15h30"),
            ("16:00", "16h00"), ("16:30", "16h30"),
            ("17:00", "17h00"), ("17:30", "17h30"),
        ]),
        ("Soir (18:00â€“23:30)", [
            ("18:00", "18h00"), ("18:30", "18h30"),
            ("19:00", "19h00"), ("19:30", "19h30"),
            ("20:00", "20h00"), ("20:30", "20h30"),
            ("21:00", "21h00"), ("21:30", "21h30"),
            ("22:00", "22h00"), ("22:30", "22h30"),
            ("23:00", "23h00"), ("23:30", "23h30"),
        ]),
    ]
    MOIS = [
        (9,'Septembre'),(10,'Octobre'),(11,'Novembre'),(12,'DÃ©cembre'),
        (1,'Janvier'),(2,'FÃ©vrier'),(3,'Mars'),(4,'Avril'),(5,'Mai'),(6,'Juin'),
    ]
    TRANCHES = [
        ('Matin', '09:00', '12:00'),
        ('AprÃ¨s-midi', '14:00', '17:00'),
        ('Soir', '19:30', '22:30'),
        ('JournÃ©e complÃ¨te', '09:00', '17:00'),
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
            # Email Ã  l'admin
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande de rÃ¨gle â€“ {demande.loge}",
                message=(
                    f"Nouvelle demande de rÃ¨gle de rÃ©currence.\n\n"
                    f"Loge      : {demande.loge}\n"
                    f"Temple    : {demande.temple}\n"
                    f"FrÃ©quence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"Horaires  : {_fmt_heure(demande.heure_debut)} â€“ {_fmt_heure(demande.heure_fin)}\n"
                    f"Mois      : {', '.join(str(m) for m in demande.mois_actifs) or 'Tous'}\n"
                    f"Demandeur : {demande.nom_demandeur} ({demande.email_demandeur})\n"
                    f"Commentaire : {demande.commentaire}\n\n"
                    f"Connectez-vous pour valider ou refuser cette demande."
                ),
                recipient_list=[get_email_admin()],
            )
            # Email de confirmation au demandeur
            send_mail_kellermann(
                subject="[Kellermann] Confirmation de votre demande de rÃ©currence",
                message=(
                    f"Bonjour {demande.nom_demandeur},\n\n"
                    f"Votre demande de rÃ¨gle de rÃ©currence a bien Ã©tÃ© reÃ§ue.\n\n"
                    f"RÃ©capitulatif :\n"
                    f"  Loge      : {demande.loge}\n"
                    f"  Temple    : {demande.temple}\n"
                    f"  FrÃ©quence : {demande.get_numero_semaine_display()} {demande.get_jour_semaine_display()}\n"
                    f"  Horaires  : {_fmt_heure(demande.heure_debut)} â€“ {_fmt_heure(demande.heure_fin)}\n\n"
                    f"RÃ©fÃ©rence : {demande.uuid}\n\n"
                    f"Vous serez informÃ©(e) par email dÃ¨s qu'elle sera traitÃ©e.\n\n"
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
    """API pour vÃ©rifier les conflits de rÃ©servation en temps rÃ©el."""
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
            'message': 'ðŸ”´ Ce crÃ©neau est dÃ©jÃ  validÃ© et occupÃ©.',
        })
    if en_attente:
        return JsonResponse({
            'conflit': True,
            'niveau': 'avertissement',
            'message': 'âš ï¸ Une demande est en cours de traitement pour ce crÃ©neau – prioritÃ© au premier demandeur.',
        })
    return JsonResponse({
        'conflit': False,
        'message': 'âœ… Ce crÃ©neau semble disponible.',
    })


# â”€â”€ Portail loge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                messages.error(request, "Le nom du VÃ©nÃ©rable et l'email sont obligatoires.")
                return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})

            loge_obj = None
            if loge_id:
                try:
                    loge_obj = Loge.objects.get(pk=loge_id)
                except Loge.DoesNotExist:
                    pass

            if not loge_obj and not nom_loge_libre:
                messages.error(request, "Veuillez sÃ©lectionner une loge ou saisir son nom.")
                return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})

            demande = DemandeAccesPortail.objects.create(
                loge=loge_obj,
                nom_loge_libre=nom_loge_libre if not loge_obj else '',
                nom_venerable=nom_venerable,
                email=email,
                message=message,
            )

            # Email Ã  l'admin
            nom_loge_display = loge_obj.nom if loge_obj else nom_loge_libre
            send_mail_kellermann(
                subject=f"[Kellermann] Nouvelle demande d'accÃ¨s portail – {nom_loge_display}",
                message=(
                    f"Nouvelle demande d'accÃ¨s au portail loge.\n\n"
                    f"Loge        : {nom_loge_display}\n"
                    f"VÃ©nÃ©rable   : {nom_venerable}\n"
                    f"Email       : {email}\n"
                    f"Message     : {message or '(aucun)'}\n\n"
                    f"Ã€ valider dans le tableau de bord d'administration."
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

            send_mail_kellermann(
                subject=f"[Kellermann] Message libre – {sujet or nom}",
                message=(
                    f"Message via le formulaire de contact.\n\n"
                    f"Nom    : {nom}\n"
                    f"Email  : {email}\n"
                    f"Sujet  : {sujet or '(non prÃ©cisÃ©)'}\n\n"
                    f"Message :\n{message}"
                ),
                recipient_list=[get_email_admin()],
            )
            return redirect('reservations:confirmation_contact')

    return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})


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

    # â”€â”€ Saison courante (par dÃ©faut) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    annee_courante = today.year if today.month >= 9 else today.year - 1

    # â”€â”€ Saison sÃ©lectionnÃ©e (GET ?saison=, sinon courante) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        annee_saison = int(request.GET.get('saison', annee_courante))
    except (ValueError, TypeError):
        annee_saison = annee_courante

    # Les 3 options proposÃ©es dans le sÃ©lecteur
    saisons_disponibles = [annee_courante - 1, annee_courante, annee_courante + 1]

    debut_saison = date_cls(annee_saison, 9, 1)
    fin_saison   = date_cls(annee_saison + 1, 6, 30)

    # â”€â”€ RÃ©servations temple : saison complÃ¨te sÃ©lectionnÃ©e, validÃ©e ou en attente â”€â”€â”€
    reservations_temple = Reservation.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut__in=['validee', 'attente'],
    ).select_related('temple').order_by('date') if loge else Reservation.objects.none()

    # RÃ©servations salle (cabinets, banquet, rÃ©union) liÃ©es Ã  la loge
    reservations_salle_qs = ReservationSalle.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut__in=['validee', 'attente'],
    ).select_related('salle').order_by('date') if loge else ReservationSalle.objects.none()

    # Normalisation en dicts uniformes pour le template
    TYPE_SALLE_LABELS = {
        'agapes': 'Agapes', 'reunion': 'Salle de rÃ©union',
        'cabinet_reflexion': 'Cabinet de rÃ©flexion',
    }

    def _temple_dict(r):
        return {
            'date': r.date, 'heure_debut': r.heure_debut, 'heure_fin': r.heure_fin,
            'statut': r.statut, 'get_statut_display': r.get_statut_display(),
            'type_code': 'temple', 'type_label': 'Temple',
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

    # Conserver aussi les querysets bruts pour compatibilitÃ© template existante
    reservations         = reservations_temple
    reservations_passees = reservations_temple.filter(date__lt=today)
    reservations_futures = reservations_temple.filter(date__gte=today)

    # â”€â”€ Validation de saison â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # La validation est indÃ©pendante du sÃ©lecteur de saison : on cherche
    # toute validation ouverte/soumise pour la loge, sans toucher Ã  annee_saison.
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

        # Email de confirmation Ã  la loge
        if loge.email:
            send_mail_kellermann(
                subject=f"Votre validation de saison {annee_saison}-{annee_saison + 1} a bien Ã©tÃ© enregistrÃ©e",
                message=(
                    f"Bonjour,\n\n"
                    f"Votre validation du calendrier pour la saison "
                    f"{annee_saison}-{annee_saison + 1} a bien Ã©tÃ© reÃ§ue.\n\n"
                    f"RÃ©capitulatif :\n"
                    f"  - {nb_ok} tenue(s) confirmÃ©e(s)\n"
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

        messages.success(request, "Votre validation a bien Ã©tÃ© enregistrÃ©e. Merci !")
        log_evenement('soumission_validation_loge',
            f"Validation saison soumise : {loge.nom} – saison {annee_saison}-{annee_saison + 1} "
            f"({nb_ok} ok, {nb_deplacer} Ã  dÃ©placer, {nb_annuler} Ã  annuler)",
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
