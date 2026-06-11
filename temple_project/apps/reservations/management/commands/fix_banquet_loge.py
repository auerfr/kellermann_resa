from django.core.management.base import BaseCommand
from temple_project.apps.reservations.models import ReservationSalle
from temple_project.apps.loges.models import Loge


class Command(BaseCommand):
    help = "Renseigne la FK loge sur les ReservationSalle agapes où loge=NULL via matching organisation=str(loge)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Affiche les correspondances sans modifier la base")

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Construire un index str(loge) → loge
        loge_index = {}
        for loge in Loge.objects.all():
            loge_index[str(loge)] = loge
            # Aussi indexer par nom seul au cas où
            loge_index[loge.nom] = loge

        orphelins = ReservationSalle.objects.filter(
            salle__type_salle='agapes',
            loge__isnull=True,
        ).select_related('salle')

        self.stdout.write(f"Banquets sans loge : {orphelins.count()}")

        fixed = 0
        unmatched = 0
        for resa in orphelins:
            org = resa.organisation or ''
            loge = loge_index.get(org)
            if loge:
                self.stdout.write(
                    f"  id={resa.id} | '{org}' -> {loge} (id={loge.id})"
                    + (" [dry-run]" if dry_run else " OK")
                )
                if not dry_run:
                    resa.loge = loge
                    resa.save(update_fields=['loge'])
                fixed += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f"  id={resa.id} | '{org}' → AUCUNE LOGE TROUVÉE")
                )
                unmatched += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n{fixed} banquet(s) corrigé(s), {unmatched} non résolus."))
        else:
            self.stdout.write(f"\n[dry-run] {fixed} seraient corrigés, {unmatched} non résolus.")
