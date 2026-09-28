"""
Management command : crée les 5 réservations Noble Amitié pour la saison 6026-6027.
Usage : python manage.py reserver_noble_amitie [--dry-run]
"""
from datetime import date, time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée les réservations Noble Amitié dans la salle Les Gobelets et les Raisins"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Simuler sans écrire en base")

    def handle(self, *args, **options):
        from temple_project.apps.reservations.models import SalleReunion, ReservationSalle
        from temple_project.apps.loges.models import Loge

        dry = options['dry_run']

        # ── Salle ───────────────────────────────────────────────────────────
        salle = SalleReunion.objects.filter(nom__icontains='Gobelets').first()
        if not salle:
            self.stderr.write("❌  Salle 'Les Gobelets et les Raisins' introuvable.")
            return
        self.stdout.write(f"✓ Salle trouvée : {salle.nom} (ID={salle.pk}, type={salle.type_salle})")

        # ── Loge ────────────────────────────────────────────────────────────
        loge = Loge.objects.filter(nom__icontains='Noble Amiti').first()
        if not loge:
            self.stderr.write("⚠  Loge 'Noble Amitié' introuvable — réservation sans loge liée.")
        else:
            self.stdout.write(f"✓ Loge trouvée : {loge.nom} (ID={loge.pk})")

        # ── Dates et types ──────────────────────────────────────────────────
        sessions = [
            (date(2026, 11, 12), "Atelier de compagnons"),
            (date(2026, 12, 10), "Atelier d'apprentis"),
            (date(2027,  2, 11), "Atelier de compagnons"),
            (date(2027,  3, 11), "Atelier d'apprenti"),
            (date(2027,  6, 10), "Atelier d'apprenti"),
        ]
        hd, hf = time(18, 0), time(22, 0)

        created = skipped = 0
        for d_r, objet in sessions:
            # Vérification de conflit
            conflit = ReservationSalle.objects.filter(
                salle=salle, date=d_r,
                heure_debut__lt=hf, heure_fin__gt=hd,
                statut__in=['attente', 'validee'],
            ).first()
            if conflit:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠  {d_r.strftime('%d/%m/%Y')} — CONFLIT avec '{conflit.nom_demandeur}' "
                    f"({conflit.heure_debut}–{conflit.heure_fin}) → ignoré"
                ))
                skipped += 1
                continue

            self.stdout.write(f"  + {d_r.strftime('%d/%m/%Y')} — {objet}")
            if not dry:
                ReservationSalle.objects.create(
                    loge=loge,
                    salle=salle,
                    date=d_r,
                    heure_debut=hd,
                    heure_fin=hf,
                    statut='validee',
                    nom_demandeur="Gregory Boyer",
                    email_demandeur="boer_gregory73@orange.fr",
                    organisation=loge.nom if loge else "Noble Amitié",
                    objet=objet,
                    nombre_participants=10,
                    type_reunion='chantier',
                    commentaire="Créé par l'administration — demande mail saison 6026-6027.",
                )
            created += 1

        label = "[DRY-RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"\n{label}{created} réservation(s) créée(s), {skipped} ignorée(s) (conflit)."
        ))
