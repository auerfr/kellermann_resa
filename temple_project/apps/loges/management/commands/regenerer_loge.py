from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from temple_project.apps.loges.models import Loge
from temple_project.apps.reservations.models import Reservation, RegleRecurrence


class Command(BaseCommand):
    help = ("Nettoie puis regenere les tenues RECURRENTES d'une (ou toutes) loge(s) "
            "pour une saison : supprime les tenues 'reguliere' residuelles de la "
            "periode, puis recree a partir des regles actuelles (respecte mois actifs "
            "et conflits avec les autres loges). N'affecte pas les tenues "
            "exceptionnelles / ponctuelles. Simulation par defaut.")

    def add_arguments(self, parser):
        parser.add_argument('abreviations', nargs='*', help="Abreviation(s) de loge (ex: YG)")
        parser.add_argument('--tous', action='store_true', help="Toutes les loges actives")
        parser.add_argument('--annee', type=int, required=True,
                            help="Annee de debut de saison (2026 = saison 2026-2027)")
        parser.add_argument('--appliquer', action='store_true', help="Execute (sinon simulation)")

    def handle(self, *args, **o):
        from temple_project.apps.administration.views import _calculer_dates_regle

        annee = o['annee']
        d1, d2 = date(annee, 9, 1), date(annee + 1, 6, 30)

        if o['tous']:
            loges = Loge.objects.filter(actif=True).order_by('nom')
        elif o['abreviations']:
            loges = Loge.objects.filter(abreviation__in=o['abreviations']).order_by('nom')
        else:
            raise CommandError("Donnez une/des abreviation(s) ou --tous.")
        if not loges:
            raise CommandError("Aucune loge correspondante.")

        tot_suppr = tot_cree = tot_conf = 0
        with transaction.atomic():
            for loge in loges:
                anciennes = Reservation.objects.filter(
                    loge=loge, type_reservation='reguliere', date__gte=d1, date__lte=d2)
                ns = anciennes.count()
                if o['appliquer']:
                    anciennes.delete()

                cree = conf = 0
                for regle in RegleRecurrence.objects.filter(loge=loge, actif=True).select_related('temple'):
                    dates = set(_calculer_dates_regle(regle, annee) + _calculer_dates_regle(regle, annee + 1))
                    exclues = set(regle.dates_exclues or [])
                    for d in sorted(dates):
                        if not (d1 <= d <= d2) or d.month in (7, 8):
                            continue
                        if d.isoformat() in exclues:
                            continue
                        if regle.date_debut and d < regle.date_debut:
                            continue
                        if regle.date_fin and d > regle.date_fin:
                            continue
                        # Conflit avec une AUTRE loge sur le meme temple/creneau
                        if Reservation.objects.filter(
                            temple=regle.temple, date=d, statut__in=['validee', 'attente'],
                            heure_debut__lt=regle.heure_fin, heure_fin__gt=regle.heure_debut,
                        ).exclude(loge=loge).exists():
                            conf += 1
                            continue
                        if o['appliquer']:
                            if not Reservation.objects.filter(
                                loge=loge, temple=regle.temple, date=d,
                                heure_debut=regle.heure_debut,
                            ).exists():
                                Reservation.objects.create(
                                    loge=loge, temple=regle.temple, date=d,
                                    heure_debut=regle.heure_debut, heure_fin=regle.heure_fin,
                                    type_reservation='reguliere', statut='validee',
                                    nom_demandeur='Generation automatique',
                                    email_demandeur=regle.loge.email or settings.DEFAULT_FROM_EMAIL,
                                    regle_source=regle,
                                )
                        cree += 1
                self.stdout.write(f"[{loge.abreviation}] {loge.nom} : -{ns} ancienne(s), +{cree} tenue(s), {conf} conflit(s)")
                tot_suppr += ns; tot_cree += cree; tot_conf += conf

            if o['appliquer']:
                self.stdout.write(self.style.SUCCESS(
                    f"\nOK : {tot_suppr} supprimee(s), {tot_cree} creee(s), {tot_conf} conflit(s) ignore(s)."))
            else:
                self.stdout.write(self.style.NOTICE(
                    f"\nSIMULATION : {tot_suppr} a supprimer, {tot_cree} a creer, {tot_conf} conflit(s). "
                    "--appliquer pour executer."))
