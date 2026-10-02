"""
Management command : trouve les créneaux récurrents libres pour un ensemble de loges.
Pour chaque "Nième JourSemaine du mois" (ex. 1er jeudi), compte combien de fois
ce créneau est disponible sur la saison, et liste les dates correspondantes.

Usage :
  python manage.py dates_libres_loges
"""
from datetime import date, timedelta
import calendar
from collections import defaultdict
from django.core.management.base import BaseCommand

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

JOURS_FR   = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
JOURS_ABBR = ["Lun",   "Mar",   "Mer",      "Jeu",   "Ven",      "Sam",    "Dim"]
RANGS_FR   = ["1er", "2e", "3e", "4e", "5e"]
MOIS_FR    = {
    9:"Septembre", 10:"Octobre", 11:"Novembre", 12:"Décembre",
    1:"Janvier",   2:"Février",  3:"Mars",       4:"Avril",
    5:"Mai",       6:"Juin",
}
MOIS_ORDRE = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


def rang_dans_mois(d):
    """Retourne le rang (0-based) du jour d dans son mois (0=1er, 1=2e…)."""
    return (d.day - 1) // 7


def nieme_jour_du_mois(annee, mois, jour_semaine, rang):
    """Retourne la date du (rang+1)-ième jour_semaine (0=lun…6=dim) du mois,
    ou None si ce rang n'existe pas ce mois-là."""
    premier = date(annee, mois, 1)
    delta = (jour_semaine - premier.weekday()) % 7
    cible = premier + timedelta(days=delta + rang * 7)
    if cible.month == mois:
        return cible
    return None


class Command(BaseCommand):
    help = "Créneaux récurrents libres pour les loges dont les membres se croisent"

    def handle(self, *args, **options):
        from temple_project.apps.loges.models import Loge
        from temple_project.apps.reservations.models import Reservation

        # ── Résoudre les loges ────────────────────────────────────────────
        loges_trouvees, loges_manquantes = [], []
        for abr in ABREVIATIONS:
            loge = Loge.objects.filter(abreviation=abr).first()
            (loges_trouvees if loge else loges_manquantes).append(loge or abr)

        loges = [l for l in loges_trouvees if l != abr or True]
        loges_obj = [l for l in loges_trouvees if hasattr(l, 'pk')]

        self.stdout.write(
            f"✓ {len(loges_obj)} loges trouvées, "
            f"{len(loges_manquantes)} introuvables : {loges_manquantes or 'aucune'}\n"
        )

        # ── Récupérer toutes les dates de tenues validées/en attente ─────
        saison_debut = date(2026, 9, 1)
        saison_fin   = date(2027, 6, 30)

        reservations = Reservation.objects.filter(
            loge__in=loges_obj,
            date__gte=saison_debut,
            date__lte=saison_fin,
            statut__in=['validee', 'attente'],
        ).values_list('date', 'loge__abreviation').order_by('date')

        dates_occupees: dict[date, list] = {}
        for d, abr in reservations:
            dates_occupees.setdefault(d, []).append(abr)

        # ── Construire la grille des créneaux récurrents ──────────────────
        # créneau = (jour_semaine 0-6, rang 0-4)
        # Pour chaque créneau, on liste les occurrences (date, libre?)
        slots: dict[tuple, list[tuple[date, bool, list]]] = defaultdict(list)

        for m in MOIS_ORDRE:
            ya = 2026 if m >= 9 else 2027
            for rang in range(5):
                for js in range(7):
                    d = nieme_jour_du_mois(ya, m, js, rang)
                    if d and saison_debut <= d <= saison_fin:
                        loges_ce_jour = dates_occupees.get(d, [])
                        libre = len(loges_ce_jour) == 0
                        slots[(js, rang)].append((d, libre, loges_ce_jour))

        # ── Résumé par créneau récurrent — trié par nb de mois libres ────
        self.stdout.write("━" * 68)
        self.stdout.write("CRÉNEAUX RÉCURRENTS — disponibilité sur la saison 2026-2027")
        self.stdout.write("(uniquement lundi–vendredi, créneaux existant ≥ 8 mois)")
        self.stdout.write("━" * 68)

        lignes = []
        for (js, rang), occurrences in slots.items():
            if js >= 5:  # samedi/dimanche : on ignore
                continue
            if len(occurrences) < 8:
                continue
            nb_libres = sum(1 for _, libre, _ in occurrences if libre)
            nb_total  = len(occurrences)
            lignes.append((nb_libres, nb_total, js, rang, occurrences))

        lignes.sort(key=lambda x: (-x[0], x[2], x[3]))

        for nb_libres, nb_total, js, rang, occurrences in lignes:
            label = f"{RANGS_FR[rang]} {JOURS_FR[js]} du mois"
            barre = "█" * nb_libres + "░" * (nb_total - nb_libres)
            self.stdout.write(f"\n  {label:<28} {nb_libres}/{nb_total}  {barre}")
            for d, libre, loges_ce_jour in occurrences:
                mois_nom = MOIS_FR[d.month]
                if libre:
                    self.stdout.write(f"    ✓ {d.strftime('%d/%m/%Y')}  {mois_nom}")
                else:
                    self.stdout.write(
                        f"    ✗ {d.strftime('%d/%m/%Y')}  {mois_nom}  ← {', '.join(loges_ce_jour)}"
                    )

        # ── Vue mensuelle des dates libres ────────────────────────────────
        self.stdout.write("\n" + "━" * 68)
        self.stdout.write("VUE MENSUELLE — dates entièrement libres")
        self.stdout.write("━" * 68)

        for m in MOIS_ORDRE:
            ya = 2026 if m >= 9 else 2027
            # Tous les jours ouvrables du mois
            libres_du_mois = []
            d = date(ya, m, 1)
            while d.month == m:
                if d.weekday() < 5 and d not in dates_occupees:
                    rang = rang_dans_mois(d)
                    libres_du_mois.append(
                        f"{JOURS_ABBR[d.weekday()]} {d.strftime('%d')} ({RANGS_FR[rang]} {JOURS_ABBR[d.weekday()]})"
                    )
                d += timedelta(days=1)

            self.stdout.write(f"\n▶ {MOIS_FR[m]} {ya}  —  {len(libres_du_mois)} jour(s) ouvrable(s) libre(s)")
            if libres_du_mois:
                # Grouper par semaine pour lisibilité
                for item in libres_du_mois:
                    self.stdout.write(f"    {item}")
            else:
                self.stdout.write("    (aucun jour ouvrable libre ce mois-ci)")

        self.stdout.write(
            f"\n  Total dates occupées : {len(dates_occupees)}  |  "
            f"Total tenues concernées : {Reservation.objects.filter(loge__in=loges_obj, date__gte=saison_debut, date__lte=saison_fin, statut__in=['validee','attente']).count()}\n"
        )
