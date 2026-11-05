"""
Management command : met à jour effectif_total des loges depuis l'ÉTAT J (col O du rapprochement).
Usage :
  python manage.py maj_effectifs_etatj --fichier /chemin/vers/fichier.xlsx [--dry-run]
"""
from django.core.management.base import BaseCommand


# Données extraites de la col O (Effectif 31/12/2025, source trésorier)
# Clé = abréviation portail exacte, Valeur = effectif
EFFECTIFS = {
    "4 SC":    37,
    "AG":      26,
    "DIV":      9,
    "ST":      40,
    "BtD":     16,
    "MC":      31,
    "CM":      15,
    "C":       38,
    "EN":      22,
    "HR":      24,
    "IM":      19,
    "IS":      27,
    "AP":      46,
    "AA":      39,
    "ES":      37,
    "NA":      60,
    "RI":      24,
    "REF":     37,
    "PHX":     14,
    "L3P":     38,
    "AL":       9,
    "AV":      63,
    "CABN":    42,
    "PL":      22,
    "18G":     38,
    "30G":     32,
    "4/14G":   47,
    "LV":      14,
    "MA":      39,
    "MHT":     26,
    "IJ":      26,
    "MVH":     31,
    "MD":      25,
    "PP":      49,
    "PdM":     27,
    "RK":      20,
    "SJ":      73,
    "Sto":     34,
    "VS":      11,
    "VI":      25,
    "VL":      12,
    "YG":      23,
    "Z":       27,
    "32G":     78,
    "UDC":     40,
    "UDLP":    33,
}

# Ces loges sont dans le fichier MAIS sans effectif col O → à signaler
SANS_EFFECTIF = [
    ("ME",    "18° Métamorphoses",                     "Haut grade"),
    ("IA",    "Ignis d'Ardens",                        "Haut grade"),
    ("CAALA", "CAALA",                                 "Loge bleue"),
    ("LSO",   "Lorraine Ste Osyth",                    "Haut grade"),
    ("PAB",   "Provinciale Austrasie Bourgogne",       "Haut grade"),
    ("AS",    "Socrate Raison et progrès",             "Loge bleue"),
    ("UDA",   "Unis dans la Diversité — Aréopage",     "Haut grade"),
    ("UDCo",  "Unis dans la Diversité — Consistoire",  "Haut grade"),
    ("18SC",  "18° Suprême Conseil de France",         "Haut grade"),
    ("30SC",  "30° Suprême Conseil de France",         "Haut grade"),
    ("PX",    "9253 Phénix",                           "Haut grade"),
]


class Command(BaseCommand):
    help = "Met à jour effectif_total depuis l'État J (col O du rapprochement trésorier)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from temple_project.apps.loges.models import Loge

        dry = options['dry_run']
        prefix = "[DRY-RUN] " if dry else ""

        updated = []
        not_found = []
        unchanged = []

        for abr, eff_new in EFFECTIFS.items():
            loge = Loge.objects.filter(abreviation=abr).first()
            if loge is None:
                not_found.append((abr, eff_new))
                continue
            eff_old = loge.effectif_total
            if eff_old == eff_new:
                unchanged.append((abr, loge.nom, eff_new))
                continue
            self.stdout.write(
                f"  {prefix}{abr:<8} — {loge.nom:<40} : {eff_old} → {eff_new}"
            )
            if not dry:
                loge.effectif_total = eff_new
                loge.save(update_fields=['effectif_total'])
            updated.append((abr, loge.nom, eff_old, eff_new))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{len(updated)} loges mises à jour, "
            f"{len(unchanged)} déjà correctes, "
            f"{len(not_found)} abréviation(s) introuvable(s) en base."
        ))

        if not_found:
            self.stdout.write(self.style.WARNING("\n⚠  Abréviations non trouvées en base :"))
            for abr, eff in not_found:
                self.stdout.write(f"   {abr:<8} (effectif attendu : {eff})")

        self.stdout.write(self.style.WARNING(
            "\n⚠  Loges/hauts grades SANS effectif dans l'État J (col O vide) :"
        ))
        for abr, nom, typ in SANS_EFFECTIF:
            self.stdout.write(f"   {abr:<8} — {nom} ({typ})")
