from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.db.models import Q, Sum
from .emails import envoyer_email_nouvelle_demande
from .models import Reservation, ReservationSalle, SalleReunion
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
            send_mail(
                subject="Confirmation de votre demande de reservation",
                message=(
                    f"Votre demande pour le {resa.date} a bien ete recue.\n"
                    f"Reference : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi/' + str(resa.uuid) + '/')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[resa.email_demandeur],
                fail_silently=True,
            )
            messages.success(request, "Votre demande a ete soumise avec succes.")
            return redirect("reservations:confirmation", uuid=resa.uuid)
    else:
        form = DemandeReservationForm()
    return render(request, "reservations/formulaire.html", {"form": form})


def soumettre_demande_salle(request):
    if request.method == "POST":
        form = DemandeReservationSalleForm(request.POST)
        if form.is_valid():
            resa = form.save(commit=False)
            resa.statut = "attente"
            resa.save()
            send_mail(
                subject="Confirmation de votre demande de salle",
                message=(
                    f"Votre demande de salle pour le {resa.date} a bien ete recue.\n"
                    f"Salle : {resa.salle}\n"
                    f"Reference : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(resa.uuid) + '/')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[resa.email_demandeur],
                fail_silently=True,
            )
            messages.success(request, "Votre demande de salle a ete soumise avec succes.")
            return redirect("reservations:confirmation_salle", uuid=resa.uuid)
    else:
        form = DemandeReservationSalleForm()
    return render(request, "reservations/formulaire_salle.html", {"form": form})


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
                return render(request, "reservations/formulaire_cabinets.html", {"form": form})

            # Créer les réservations pour chaque cabinet demandé
            cabinets_libres = SalleReunion.objects.filter(
                type_salle='cabinet_reflexion',
                actif=True
            ).exclude(
                # Exclure les cabinets déjà réservés sur ce créneau
                Q(reservations__date=date) &
                Q(reservations__heure_debut__lt=heure_fin) &
                Q(reservations__heure_fin__gt=heure_debut) &
                Q(reservations__statut__in=['attente', 'validee'])
            ).distinct()[:nombre_cabinets_demandes]

            if len(cabinets_libres) < nombre_cabinets_demandes:
                messages.error(request, "Erreur interne : pas assez de cabinets libres trouvés.")
                return render(request, "reservations/formulaire_cabinets.html", {"form": form})

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
                    nombre_cabinets=1,  # Chaque réservation ne réserve qu'un cabinet
                    commentaire=form.cleaned_data['commentaire']
                )
                reservations_creees.append(resa)

            # Envoyer un email de confirmation
            send_mail(
                subject="Confirmation de votre demande de cabinets de réflexion",
                message=(
                    f"Votre demande de {nombre_cabinets_demandes} cabinet(s) de réflexion "
                    f"pour le {date} de {heure_debut} à {heure_fin} a bien été reçue.\n"
                    f"Référence(s) : {', '.join([str(r.uuid) for r in reservations_creees])}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(reservations_creees[0].uuid) + '/')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[form.cleaned_data['email_demandeur']],
                fail_silently=True,
            )

            messages.success(request, f"Votre demande de {nombre_cabinets_demandes} cabinet(s) a été soumise avec succès.")
            return redirect("reservations:confirmation_salle", uuid=reservations_creees[0].uuid)
    else:
        form = DemandeCabinetsForm()

    return render(request, "reservations/formulaire_cabinets.html", {"form": form})


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

        # Compter les cabinets déjà réservés sur ce créneau
        from django.db.models import Sum
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

        return JsonResponse({
            'cabinets_disponibles': max(0, cabinets_disponibles),
            'total_cabinets': total_cabinets_disponibles,
            'cabinets_reserves': reservations_existantes
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
            send_mail(
                subject="Confirmation de votre demande de banquet d'ordre",
                message=(
                    f"Votre demande de banquet d'ordre pour le {date} "
                    f"de {heure_debut} à {heure_fin} a bien été reçue.\n"
                    f"Nombre de repas : {form.cleaned_data['nombre_repas']}\n"
                    f"Référence : {resa.uuid}\n"
                    f"Vous pouvez suivre votre demande sur : "
                    f"{request.build_absolute_uri('/reservations/suivi-salle/' + str(resa.uuid) + '/')}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[form.cleaned_data['email_demandeur']],
                fail_silently=True,
            )

            messages.success(request, "Votre demande de banquet d'ordre a été soumise avec succès.")
            return redirect("reservations:confirmation_banquet", uuid=resa.uuid)
    else:
        form = DemandeBanquetForm()

    return render(request, "reservations/formulaire_banquet.html", {"form": form})


def confirmation_banquet(request, uuid):
    resa = get_object_or_404(ReservationSalle, uuid=uuid)
    return render(request, "reservations/confirmation_banquet.html", {"reservation": resa})


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
