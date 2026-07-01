from django.core.management.base import BaseCommand
from django.db import transaction

from temple_project.apps.loges.models import Loge
from temple_project.apps.reservations.models import (
    Reservation, ReservationSalle, RegleRecurrence,
)


class Command(BaseCommand):
    help = ("Supprime definitivement une ou plusieurs loges (doublons) ET toutes "
            "leurs donnees : regles de recurrence, reservations temple et salle. "
            "Simulation par defaut ; --appliquer pour executer.")

    def add_arguments(self, parser):
        parser.add_argument('abreviations', nargs='+',
                            help="Abreviation(s) des loges a supprimer (ex: 18GO 30GO 14GO)")
        parser.add_argument('--appliquer', action='store_true',
                            help="Execute reellement (sinon simulation)")

    def handle(self, *args, **opts):
        with transaction.atomic():
            for ab in opts['abreviations']:
                loges = list(Loge.objects.filter(abreviation__iexact=ab))
                if not loges:
                    self.stdout.write(self.style.WARNING(f"[{ab}] introuvable"))
                    continue
                for loge in loges:
                    nr = RegleRecurrence.objects.filter(loge=loge).count()
                    nt = Reservation.objects.filter(loge=loge).count()
                    ns = ReservationSalle.objects.filter(loge=loge).count()
                    self.stdout.write(
                        f"[{ab}] pk={loge.pk} \"{loge.nom}\" : "
                        f"{nr} regle(s), {nt} tenue(s) temple, {ns} resa salle  -> SUPPRESSION")
                    if opts['appliquer']:
                        Reservation.objects.filter(loge=loge).delete()
                        ReservationSalle.objects.filter(loge=loge).delete()
                        RegleRecurrence.objects.filter(loge=loge).delete()
                        loge.delete()

            if opts['appliquer']:
                self.stdout.write(self.style.SUCCESS("\nSuppression effectuee."))
            else:
                self.stdout.write(self.style.NOTICE(
                    "\n(SIMULATION - relancez avec --appliquer pour supprimer reellement.)"))
