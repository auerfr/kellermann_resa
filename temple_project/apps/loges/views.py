from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from temple_project.apps.auth_custom.views import membre_required
from django.contrib import messages
from django.db.models import Count, Q
from datetime import date
from .models import Loge, Obedience
from temple_project.apps.reservations.models import Reservation, ReservationSalle, Temple


@membre_required
def liste_loges(request):
    # Filtres
    filtre_obd    = request.GET.get('obedience', '')
    filtre_type   = request.GET.get('type', '')
    filtre_search = request.GET.get('q', '')
    filtre_rite   = request.GET.get('rite', '')
    tri           = request.GET.get('tri', 'nom')

    loges = Loge.objects.select_related("obedience").filter(actif=True)

    if filtre_obd:
        loges = loges.filter(obedience__nom=filtre_obd)
    if filtre_type:
        loges = loges.filter(type_loge=filtre_type)
    if filtre_search:
        loges = loges.filter(
            Q(nom__icontains=filtre_search) | Q(abreviation__icontains=filtre_search)
        )
    if filtre_rite:
        loges = loges.filter(rite=filtre_rite)

    # Annoter avec le nombre de tenues cette saison
    annee = date.today().year
    loges = loges.annotate(
        nb_tenues=Count(
            'reservations',
            filter=Q(
                reservations__date__year=annee,
                reservations__statut='validee'
            )
        )
    ).order_by(tri)

    obediences = Obedience.objects.all().order_by('nom')

    context = {
        'loges':       loges,
        'obediences':  obediences,
        'filtre_obd':  filtre_obd,
        'filtre_type': filtre_type,
        'filtre_search': filtre_search,
        'filtre_rite': filtre_rite,
        'tri':         tri,
        'nb_total':    loges.count(),
        'annee':       annee,
    }
    return render(request, "loges/liste.html", context)


@membre_required
def detail_loge(request, pk):
    loge = get_object_or_404(Loge, pk=pk, actif=True)

    annee = date.today().year
    saison_defaut = annee if date.today().month >= 9 else annee - 1
    annee_param = int(request.GET.get('annee', saison_defaut))
    debut_saison = date(annee_param, 9, 1)
    fin_saison   = date(annee_param + 1, 6, 30)

    # Tenues temple de la saison demandée
    tenues = Reservation.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut='validee'
    ).select_related('temple').order_by('date')

    # Réservations salle de la saison demandée
    resas_salle = ReservationSalle.objects.filter(
        loge=loge,
        date__gte=debut_saison,
        date__lte=fin_saison,
        statut__in=['validee', 'attente'],
    ).select_related('salle').order_by('date')

    # Normalisation en dicts uniformes
    TYPE_SALLE_LABELS = {
        'agapes': 'Agapes', 'reunion': 'Salle de réunion',
        'cabinet_reflexion': 'Cabinet de réflexion',
    }

    def _t(r):
        return {
            'date': r.date, 'heure_debut': r.heure_debut, 'heure_fin': r.heure_fin,
            'statut': r.statut, 'get_statut_display': r.get_statut_display(),
            'type_code': 'temple', 'type_label': 'Temple',
            'lieu': str(r.temple) if r.temple else '—',
            'detail': '',
        }

    def _s(r):
        ts = r.salle.type_salle if r.salle else ''
        return {
            'date': r.date, 'heure_debut': r.heure_debut, 'heure_fin': r.heure_fin,
            'statut': r.statut, 'get_statut_display': r.get_statut_display(),
            'type_code': ts, 'type_label': TYPE_SALLE_LABELS.get(ts, ts),
            'lieu': str(r.salle) if r.salle else '—',
            'detail': r.objet or '',
        }

    from itertools import chain
    tous_evenements = sorted(
        chain((_t(r) for r in tenues), (_s(r) for r in resas_salle)),
        key=lambda d: d['date'],
    )

    # Stats par temple
    stats_temples = {}
    for temple in Temple.objects.all():
        nb = tenues.filter(temple=temple).count()
        if nb > 0:
            stats_temples[str(temple)] = nb

    # Historique demandes exceptionnelles
    demandes = Reservation.objects.filter(
        loge=loge,
        type_reservation='exceptionnelle'
    ).order_by('-date')[:10]

    # Prochaine tenue
    prochaine = Reservation.objects.filter(
        loge=loge,
        date__gte=date.today(),
        statut='validee'
    ).order_by('date').first()

    context = {
        'loge':            loge,
        'tenues':          tenues,
        'tous_evenements': tous_evenements,
        'stats_temples':   stats_temples,
        'demandes':        demandes,
        'prochaine':       prochaine,
        'annee':           annee_param,
        'annees':          [annee - 2, annee - 1, annee],
        'saison_label':    f"{annee_param}/{annee_param+1}",
        'nb_tenues':       tenues.count(),
    }
    return render(request, "loges/detail.html", context)


@membre_required
def modifier_loge(request, pk):
    loge = get_object_or_404(Loge, pk=pk)

    if not request.user.is_staff:
        messages.error(request, "Accès non autorisé.")
        return redirect('loges:liste')

    if request.method == 'POST':
        loge.nom                    = request.POST.get('nom', loge.nom)
        loge.abreviation            = request.POST.get('abreviation', loge.abreviation)
        loge.email                  = request.POST.get('email', loge.email)
        loge.effectif_total         = int(request.POST.get('effectif_total', 0) or 0)
        loge.effectif_moyen_agapes  = int(request.POST.get('effectif_moyen_agapes', 0) or 0)
        obd_nom = request.POST.get('obedience')
        if obd_nom:
            obd, _ = Obedience.objects.get_or_create(nom=obd_nom)
            loge.obedience = obd
        loge.type_loge = request.POST.get('type_loge', loge.type_loge)
        loge.rite           = request.POST.get('rite', loge.rite)
        loge.rite_precision = request.POST.get('rite_precision', '').strip()
        loge.save()
        messages.success(request, f"Loge {loge.nom} modifiée avec succès.")
        return redirect('loges:detail', pk=loge.pk)

    obediences = Obedience.objects.all().order_by('nom')
    return render(request, "loges/modifier.html", {
        'loge':       loge,
        'obediences': obediences,
    })


@membre_required
def supprimer_loge(request, pk):
    loge = get_object_or_404(Loge, pk=pk)

    if not request.user.is_staff:
        messages.error(request, "Accès non autorisé.")
        return redirect('loges:liste')

    if request.method == 'POST':
        # Désactivation plutôt que suppression physique
        loge.actif = False
        loge.save()
        messages.success(request, f"Loge {loge.nom} désactivée.")
        return redirect('loges:liste')

    return render(request, "loges/supprimer.html", {'loge': loge})
