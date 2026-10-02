"""
Management command : trouve les dates sans tenue pour un ensemble de loges.
Affiche, mois par mois, les jours où AUCUNE des loges listées n'a de réservation.

Usage :
  python manage.py dates_libres_loges
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand

# Loges citées par l'utilisateur — abréviations portail
ABREVIATIONS = [
    "MC",    # Chapitre Marc Chagall
    "IJ",    # Maître Inigo Jones
    "AP",    # L'Arbre et la Pierre
    "18G",   # Vrais Amis de Metz 18°
    "30G",   # Vrais Amis de Metz 30°
    "4/14G", # Vrais Amis de Metz 4°/14°
    "Sto",   # Stoa
    "MA",    # Maât
    "PHX",   # Le Phénix N°X
    "PX",    # 9253 Phénix
    "LV",    # Léonard de Vinci
    "CM",    # Clément de Metz
    "MD",    # Médiation
    "IM",    # Ici et Maintenant
    "YG",    # Yggdrasill
    "ME",    # 18° Métamorphoses
    "ST",    # Aréopage Stanislas
    "RK",    # Rudyard Kipling
    "VL",    # Voix de la Liberté
    "PP",    # Pierre Perrat à l'Étoile Flamboyante
    "REF",   # République à l'École de la Fraternité
]

JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR  = {
    9:"Septembre", 10:"Octobre", 11:"Novembre", 12:"Décembre",
    1:"Janvier", 2:"Février", 3:"Mars", 4:"Avril", 5:"Mai", 6:"Juin"
}


class Command(BaseCommand):
    help = "Dates sans tenue pour les loges dont les membres se croisent"

    def handle(self, *args, **options):
        from temple_project.apps.loges.models import Loge
        from temple_project.apps.reservations.models import Reservation

        # ── Résoudre les loges ────────────────────────────────────────────
        loges_trouvees = []
        loges_manquantes = []
        for abr in ABREVIATIONS:
            loge = Loge.objects.filter(abreviation=abr).first()
            if loge:
                loges_trouvees.append(loge)
            else:
                loges_manquantes.append(abr)

        self.stdout.write(f"✓ {len(loges_trouvees)} loges trouvées, {len(loges_manquantes)} introuvables : {loges_manquantes or 'aucune'}\n")

        # ── Récupérer toutes les dates de tenues validées/en attente ─────
        saison_debut = date(2026, 9, 1)
        saison_fin   = date(2027, 6, 30)

        reservations = Reservation.objects.filter(
            loge__in=loges_trouvees,
            date__gte=saison_debut,
            date__lte=saison_fin,
            statut__in=['validee', 'attente'],
        ).select_related('loge').order_by('date')

        # Construire dict date → liste de loges occupées
        dates_occupees: dict = {}
        for r in reservations:
            dates_occupees.setdefault(r.date, []).append(r.loge.abreviation)

        # ── Afficher mois par mois ────────────────────────────────────────
        self.stdout.write("━" * 60)
        self.stdout.write("DATES AVEC TENUE(S) — saison 2026-2027")
        self.stdout.write("━" * 60)

        for m in [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]:
            ya = 2026 if m >= 9 else 2027
            self.stdout.write(f"\n▶ {MOIS_FR[m]} {ya}")
            d = date(ya, m, 1)
            mois_occupes = {k: v for k, v in dates_occupees.items() if k.month == m and k.year == ya}
            if not mois_occupes:
                self.stdout.write("  → Aucune tenue ce mois-ci pour ces loges.")
            else:
                for d_r in sorted(mois_occupes):
                    loges_ce_jour = ", ".join(mois_occupes[d_r])
                    self.stdout.write(
                        f"  {JOURS_FR[d_r.weekday()]} {d_r.strftime('%d/%m/%Y')}  ←  {loges_ce_jour}"
                    )

        # ── Résumé : jours de semaine récurrents dégagés ─────────────────
        self.stdout.write("\n" + "━" * 60)
        self.stdout.write("RÉSUMÉ — jours de semaine sans aucune tenue de ces loges")
        self.stdout.write("━" * 60)
        # Compter par jour de semaine les dates occupées
        jours_charges = {j: 0 for j in range(7)}
        for d_r in dates_occupees:
            jours_charges[d_r.weekday()] += 1

        total_dates = (saison_fin - saison_debut).days + 1
        nb_semaines = total_dates // 7
        self.stdout.write("")
        for j, nom in enumerate(JOURS_FR):
            nb = jours_charges[j]
            self.stdout.write(f"  {nom} : {nb} tenue(s) — {nb_semaines - nb} {nom.lower()}s libres sur {nb_semaines}")

        self.stdout.write(f"\n  Total dates occupées : {len(dates_occupees)} sur ~{nb_semaines * 5} jours ouvrables")
        self.stdout.write(f"  Total tenues concernées : {reservations.count()}\n")
