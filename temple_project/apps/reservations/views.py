import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from temple_project.apps.administration.email_utils import send_mail_kellermann, get_email_admin
from django.db.models import Q, Sum
from .emails import envoyer_email_nouvelle_demande
from .models import Reservation, ReservationSalle, SalleReunion, DemandeRegleRecurrence, RegleRecurrence, Temple, DemandeAccesPortail
from temple_project.apps.loges.models import Loge
from .forms import DemandeReservationForm, DemandeReservationSalleForm, DemandeCabinetsForm, DemandeBanquetForm


def soumettre_demande(request):
    if request.method == "POST":
        form = DemandeReservationForm(request.POST)
        if form.is_valid():
            resa = form.save(commit=False)
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
    return render(request, "reservations/formulaire.html", {"form": form})


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
    salle_banquet = SalleReunion.objects.filter(type_salle='agapes', actif=True).first()
    if not salle_banquet:
        messages.error(request, "Aucune salle de banquet n'est disponible.")
        return redirect('reservations:demande')

    if request.method == "POST":
        form = DemandeBanquetForm(request.POST)
        if form.is_valid():
            # Vérifier la disponibilité de la salle
            date = form.cleaned_data['date']
            heure_debut = form.cleaned_data['heure_debut']
            heure_fin = form.cleaned_data['heure_fin']

            # Vérifier s'il y a déjà une réservation sur ce créneau
            conflit = ReservationSalle.objects.filter(
                salle=salle_banquet,
                date=date,
                heure_debut__lt=heure_fin,
                heure_fin__gt=heure_debut,
                statut__in=['attente', 'validee']
            ).exists()

            if conflit:
                messages.error(request, "La salle n'est pas disponible sur ce créneau.")
                return render(request, "reservations/formulaire_banquet.html", {"form": form})

            # Créer la réservation
            resa = ReservationSalle.objects.create(
                salle=salle_banquet,
                date=date,
                heure_debut=heure_debut,
                heure_fin=heure_fin,
                statut="attente",
                nom_demandeur=form.cleaned_data['nom_demandeur'],
                email_demandeur=form.cleaned_data['email_demandeur'],
                organisation=str(form.cleaned_data['loge']),
                objet="Banquet d'ordre",
                nombre_participants=form.cleaned_data['nombre_repas'],  # Utiliser nombre_repas pour participants
                nombre_cabinets=1,  # Pas applicable pour banquet
                commentaire=form.cleaned_data['commentaire']
            )

            # Envoyer un email de confirmation
            send_mail_kellermann(
                subject="Confirmation de votre demande de banquet d'ordre",
                message=(
                    f"Votre demande de banquet d'ordre pour le {date} "
                    f"de {heure_debut} à {heure_fin} a bien été reçue.\n"
                    f"Nombre de repas : {form.cleaned_data['nombre_repas']}\n"
                    f"Référence : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(resa.uuid) + '/')}"
                ),
                recipient_list=[form.cleaned_data['email_demandeur']],
            )

            messages.success(request, "Votre demande de banquet d'ordre a été soumise avec succès.")
            return redirect("reservations:confirmation_banquet", uuid=resa.uuid)
    else:
        form = DemandeBanquetForm()

    return render(request, "reservations/formulaire_banquet.html", {"form": form})


def confirmation_banquet(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    return render(request, "reservations/confirmation_banquet.html", {"reservation": resa})


def soumettre_demande_recurrence(request):
    """Formulaire front-end : une loge demande une règle de récurrence."""
    HORAIRES = [
        ('09:00','09h00'),('09:30','09h30'),('10:00','10h00'),('10:30','10h30'),
        ('11:00','11h00'),('11:30','11h30'),('12:00','12h00'),
        ('14:00','14h00'),('14:30','14h30'),('15:00','15h00'),('15:30','15h30'),
        ('16:00','16h00'),('16:30','16h30'),('17:00','17h00'),
        ('19:00','19h00'),('19:30','19h30'),('20:00','20h00'),('20:30','20h30'),
        ('21:00','21h00'),('22:00','22h00'),('22:30','22h30'),('23:00','23h00'),
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
                    f"Horaires  : {demande.heure_debut:%H:%M} – {demande.heure_fin:%H:%M}\n"
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
                    f"  Horaires  : {demande.heure_debut:%H:%M} – {demande.heure_fin:%H:%M}\n\n"
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
        'horaires': HORAIRES,
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
    temple = request.GET.get('temple')
    date = request.GET.get('date')
    heure_debut = request.GET.get('heure_debut')
    heure_fin = request.GET.get('heure_fin')

    if not all([temple, date, heure_debut, heure_fin]):
        return JsonResponse({'conflit': False, 'message': ''})

    # Vérifier les conflits
    conflits = Reservation.objects.filter(
        temple=temple,
        date=date,
        statut__in=['validee', 'attente'],
    ).filter(
        Q(heure_debut__lt=heure_fin, heure_fin__gt=heure_debut)
    ).exclude(statut='refusee')

    conflit = conflits.exists()

    return JsonResponse({
        'conflit': conflit,
        'message': '⚠️ Attention — Ce créneau est déjà occupé sur ce temple. Votre demande sera soumise mais pourrait être refusée.' if conflit else '✅ Ce créneau semble disponible.'
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
                subject=f"[Kellermann] Nouvelle demande d'accès portail — {nom_loge_display}",
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

            send_mail_kellermann(
                subject=f"[Kellermann] Message libre — {sujet or nom}",
                message=(
                    f"Message via le formulaire de contact.\n\n"
                    f"Nom    : {nom}\n"
                    f"Email  : {email}\n"
                    f"Sujet  : {sujet or '(non précisé)'}\n\n"
                    f"Message :\n{message}"
                ),
                recipient_list=[get_email_admin()],
            )
            return redirect('reservations:confirmation_contact')

    return render(request, 'reservations/contact.html', {'loges': loges, 'onglet': 'acces'})


def confirmation_contact(request):
    return render(request, 'reservations/confirmation_contact.html')


def portail_loge(request, token):
    demande = get_object_or_404(DemandeAccesPortail, token=token, statut='validee')

    from datetime import date as date_cls
    today = date_cls.today()

    reservations = Reservation.objects.filter(
        loge=demande.loge,
        date__gte=today,
        statut='validee',
    ).select_related('temple').order_by('date') if demande.loge else Reservation.objects.none()

    return render(request, 'reservations/portail_loge.html', {
        'demande':      demande,
        'reservations': reservations,
        'loge':         demande.loge,
    })
