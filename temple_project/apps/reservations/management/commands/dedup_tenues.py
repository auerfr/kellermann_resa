from collections import defaultdict
from datetime import date as _date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from temple_project.apps.loges.models import Loge
from temple_project.apps.reservations.models import Reservation


class Command(BaseCommand):
    help = ("Supprime les tenues d'une loge qui se CHEVAUCHENT le meme jour "
            "(ex: une tenue recurrente + une ponctuelle sur un autre temple a la "
            "meme heure). On conserve en priorite la tenue recurrente, sinon la plus "
            "ancienne. Simulation par defaut.")

    def add_arguments(self, parser):
        parser.add_argument('abreviations', nargs='*', help="Abreviation(s) de loge")
        parser.add_argument('--tous', action='store_true', help="Toutes les loges")
        parser.add_argument('--annee', type=int, help="Limiter a la saison (2026 = 2026-2027)")
        parser.add_argument('--appliquer', action='store_true', help="Execute (sinon simulation)")

    def handle(self, *args, **o):
        if o['tous']:
            loges = Loge.objects.all().order_by('nom')
        elif o['abreviations']:
            loges = Loge.objects.filter(abreviation__in=o['abreviations']).order_by('nom')
        else:
            raise CommandError("Donnez une/des abreviation(s) ou --tous.")

        bornes = None
        if o.get('annee'):
            bornes = (_date(o['annee'], 9, 1), _date(o['annee'] + 1, 6, 30))

        def prio(r):
            return (0 if r.type_reservation == 'reguliere' else 1, r.id)

        total = 0
        with transaction.atomic():
            for loge in loges:
                qs = Reservation.objects.filter(loge=loge, statut__in=['validee', 'attente'])
                if bornes:
                    qs = qs.filter(date__gte=bornes[0], date__lte=bornes[1])
                par_jour = defaultdict(list)
                for r in qs:
                    par_jour[r.date].append(r)

                a_suppr = []
                for d, items in par_jour.items():
                    if len(items) < 2:
                        continue
                    items.sort(key=prio)
                    gardes = []
                    for r in items:
                        if any(r.heure_debut < g.heure_fin and r.heure_fin > g.heure_debut
                               for g in gardes):
                            a_suppr.append(r)
                        else:
                            gardes.append(r)

                if a_suppr:
                    self.stdout.write(f"[{loge.abreviation}] {loge.nom} : {len(a_suppr)} tenue(s) en doublon")
                    for r in a_suppr:
                        self.stdout.write(f"    x {r.date} {r.temple} {r.heure_debut}-{r.heure_fin} "
                                          f"({r.type_reservation})")
                        if o['appliquer']:
                            r.delete()
                    total += len(a_suppr)

            if o['appliquer']:
                self.stdout.write(self.style.SUCCESS(f"\n{total} tenue(s) en doublon supprimee(s)."))
            else:
                self.stdout.write(self.style.NOTICE(
                    f"\nSIMULATION : {total} tenue(s) a supprimer. --appliquer pour executer."))
