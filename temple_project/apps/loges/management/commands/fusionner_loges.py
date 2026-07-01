from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from temple_project.apps.loges.models import Loge


class Command(BaseCommand):
    help = ("Fusionne deux loges en double : réaffecte toutes les données "
            "(règles, réservations, validations, accès portail…) à la loge "
            "conservée, puis supprime l'autre. Simulation par défaut.")

    def add_arguments(self, parser):
        parser.add_argument('terme', nargs='?', help="Terme de recherche (nom ou abréviation)")
        parser.add_argument('--garder', type=int, help="pk de la loge à conserver")
        parser.add_argument('--supprimer', type=int, help="pk de la loge à supprimer")
        parser.add_argument('--appliquer', action='store_true',
                            help="Exécute réellement (sinon simulation)")

    def _nb_lies(self, loge):
        return sum(rel.related_model.objects.filter(**{rel.field.name: loge}).count()
                   for rel in Loge._meta.related_objects)

    def handle(self, *args, **opts):
        if opts.get('garder') and opts.get('supprimer'):
            garder = Loge.objects.filter(pk=opts['garder']).first()
            suppr = Loge.objects.filter(pk=opts['supprimer']).first()
            if not garder or not suppr:
                raise CommandError("pk introuvable(s).")
        else:
            terme = opts.get('terme')
            if not terme:
                raise CommandError("Fournir un terme de recherche, ou --garder et --supprimer.")
            qs = list(Loge.objects.filter(
                Q(nom__icontains=terme) | Q(abreviation__iexact=terme)).order_by('pk'))
            self.stdout.write(f"{len(qs)} loge(s) trouvée(s) pour « {terme} » :")
            for l in qs:
                self.stdout.write(f"  pk={l.pk} [{l.abreviation}] {l.nom} - "
                                  f"{self._nb_lies(l)} objet(s) lié(s) - statut {l.statut}")
            if len(qs) != 2:
                raise CommandError("Il faut exactement 2 loges (sinon utilisez --garder/--supprimer).")
            qs.sort(key=self._nb_lies, reverse=True)   # on garde la plus « riche »
            garder, suppr = qs[0], qs[1]

        if garder.pk == suppr.pk:
            raise CommandError("Les deux loges sont identiques.")

        self.stdout.write(self.style.WARNING(
            f"\nFUSION : conserver pk={garder.pk} « {garder.nom} »  <=  "
            f"supprimer pk={suppr.pk} « {suppr.nom} »"))

        report = {}
        with transaction.atomic():
            # Cas particulier : ValidationSaison est unique par (loge, année)
            from temple_project.apps.reservations.models import ValidationSaison
            annees = set(ValidationSaison.objects.filter(loge=garder).values_list('annee', flat=True))
            conflits = ValidationSaison.objects.filter(loge=suppr, annee__in=annees)
            if conflits.exists():
                report['ValidationSaison (doublons supprimés)'] = conflits.count()
                if opts['appliquer']:
                    conflits.delete()

            # Réaffectation générique de toutes les clés étrangères pointant vers Loge
            for rel in Loge._meta.related_objects:
                fname = rel.field.name
                Model = rel.related_model
                base = Model.objects.filter(**{fname: suppr})
                n = base.count()
                if n:
                    report[f"{Model._meta.verbose_name} ({fname})"] = n
                    if opts['appliquer']:
                        base.update(**{fname: garder})

            # Complète les infos manquantes de la loge conservée
            for champ in ('email', 'telephone', 'nom_contact', 'rite', 'rite_precision'):
                if not getattr(garder, champ) and getattr(suppr, champ):
                    setattr(garder, champ, getattr(suppr, champ))

            if opts['appliquer']:
                garder.save()
                suppr.delete()

        self.stdout.write("\nObjets réaffectés :")
        if report:
            for k, v in report.items():
                self.stdout.write(f"  {k} : {v}")
        else:
            self.stdout.write("  (aucun objet lié à la loge supprimée)")

        if opts['appliquer']:
            self.stdout.write(self.style.SUCCESS(
                f"\nFusion effectuée. Loge conservée : pk={garder.pk} « {garder.nom} »."))
        else:
            self.stdout.write(self.style.NOTICE(
                "\n(SIMULATION - relancez avec --appliquer pour exécuter réellement.)"))
