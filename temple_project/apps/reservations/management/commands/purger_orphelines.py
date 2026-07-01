from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from temple_project.apps.reservations.models import Reservation, ReservationSalle


class Command(BaseCommand):
    help = ("Supprime les tenues et reservations de salle ORPHELINES (sans loge), "
            "residus d'une loge supprimee qui restent affiches sur le calendrier. "
            "Simulation par defaut ; --appliquer pour executer.")

    def add_arguments(self, parser):
        parser.add_argument('--appliquer', action='store_true',
                            help="Execute reellement (sinon simulation)")
        parser.add_argument('--tout', action='store_true',
                            help="Supprime AUSSI les orphelines non-recurrentes "
                                 "(exceptionnelle/congres/salle) - attention aux "
                                 "vraies demandes externes sans loge.")

    def handle(self, *args, **o):
        temple = Reservation.objects.filter(loge__isnull=True)
        salle = ReservationSalle.objects.filter(loge__isnull=True)
        if not o['tout']:
            temple = temple.filter(type_reservation='reguliere')
            salle = salle.none()

        self.stdout.write(f"Tenues temple sans loge : {temple.count()}")
        for t, n in sorted(Counter(temple.values_list('type_reservation', flat=True)).items()):
            self.stdout.write(f"   {t} : {n}")
        self.stdout.write(f"Reservations de salle sans loge : {salle.count()}")

        with transaction.atomic():
            if o['appliquer']:
                nt = temple.count()
                ns = salle.count()
                temple.delete()
                salle.delete()
                self.stdout.write(self.style.SUCCESS(
                    f"\nOK : {nt} tenue(s) et {ns} reservation(s) de salle supprimee(s)."))
            else:
                self.stdout.write(self.style.NOTICE(
                    "\nSIMULATION - relancez avec --appliquer pour supprimer reellement."))
