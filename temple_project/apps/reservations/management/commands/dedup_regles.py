from django.core.management.base import BaseCommand
from django.db.models import Count

from temple_project.apps.reservations.models import RegleRecurrence


class Command(BaseCommand):
    help = ("Supprime les regles de recurrence en double (meme loge/temple/jour/"
            "numero de semaine), en conservant la plus ancienne. Simulation par defaut.")

    def add_arguments(self, parser):
        parser.add_argument('--appliquer', action='store_true',
                            help="Execute reellement (sinon simulation)")

    def handle(self, *args, **opts):
        cles = (RegleRecurrence.objects
                .values('loge', 'temple', 'jour_semaine', 'numero_semaine')
                .annotate(n=Count('id')).filter(n__gt=1))
        total = 0
        for c in cles:
            regles = RegleRecurrence.objects.filter(
                loge=c['loge'], temple=c['temple'],
                jour_semaine=c['jour_semaine'], numero_semaine=c['numero_semaine'],
            ).select_related('loge', 'temple').order_by('id')
            garder = regles.first()
            extras = regles.exclude(pk=garder.pk)
            n = extras.count()
            total += n
            self.stdout.write(
                f"{garder.loge} | {garder.temple} | jour {garder.jour_semaine} "
                f"sem {garder.numero_semaine} : {n} doublon(s) -> on garde id={garder.pk}")
            if opts['appliquer']:
                extras.delete()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Aucun doublon de regle."))
        elif opts['appliquer']:
            self.stdout.write(self.style.SUCCESS(f"{total} doublon(s) supprime(s)."))
        else:
            self.stdout.write(self.style.NOTICE(
                f"{total} doublon(s) detecte(s) - relancez avec --appliquer pour supprimer."))
