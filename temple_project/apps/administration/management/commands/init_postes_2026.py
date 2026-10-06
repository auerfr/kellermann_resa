"""
Peuple les PosteCharge pour la saison 2026 à partir du Compte de Résultat 2026
(réel 8 mois + prévisionnel 12 mois, arrêté au 31/08/2026).

Budget de référence : 107 822 € (charges d'exploitation) + 3 400 € amortissements
= 111 222 € de coûts de fonctionnement complets.

Usage :
    python manage.py init_postes_2026
    python manage.py init_postes_2026 --saison 2026   # saison 2026-2027
    python manage.py init_postes_2026 --force          # réinitialise si déjà existants
    python manage.py init_postes_2026 --sans-amortissements  # exclut les 3 400 € d'amortissements
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from temple_project.apps.administration.models import PosteCharge


# ── Postes de base : charges d'exploitation 2026 ─────────────────────────────
# Source : Compte de résultat 31/08/2026 – colonne "2026(12 mois) prévisionnel"
# Total exploitation : 107 822,32 €

POSTES_EXPLOITATION = [

    # ── Mutualisés : énergie — partagée entre les cohabitats du même jour ─────
    dict(libelle="Eau",                                  type_charge='mutualise', montant=Decimal('2500'),   unite='annuel'),
    dict(libelle="Électricité",                          type_charge='mutualise', montant=Decimal('21800'),  unite='annuel'),
    dict(libelle="Gaz",                                  type_charge='mutualise', montant=Decimal('27500'),  unite='annuel'),
    # Sous-total mutualisé : 51 800 €

    # ── Fixes : structure — répartis sur l'ensemble des tenues de la saison ───
    dict(libelle="Petit équipement (temples)",           type_charge='fixe', montant=Decimal('600'),    unite='annuel'),
    dict(libelle="Entretien et réparations (intérieur)", type_charge='fixe', montant=Decimal('13000'),  unite='annuel'),
    dict(libelle="Entretien et réparations (extérieur)", type_charge='fixe', montant=Decimal('2200'),   unite='annuel'),
    dict(libelle="Maintenance chauffage",                type_charge='fixe', montant=Decimal('13500'),  unite='annuel'),
    dict(libelle="Contrôle incendie et autres",          type_charge='fixe', montant=Decimal('972'),    unite='annuel'),
    dict(libelle="Assurance multirisques",               type_charge='fixe', montant=Decimal('1125'),   unite='annuel'),
    dict(libelle="Assurance risques financiers",         type_charge='fixe', montant=Decimal('448'),    unite='annuel'),
    dict(libelle="Abonnement + affranchissements",       type_charge='fixe', montant=Decimal('600'),    unite='annuel'),
    dict(libelle="Services bancaires",                   type_charge='fixe', montant=Decimal('280'),    unite='annuel'),
    dict(libelle="Réceptions",                           type_charge='fixe', montant=Decimal('30'),     unite='annuel'),
    dict(libelle="Taxe ordures ménagères",               type_charge='fixe', montant=Decimal('1000'),   unite='annuel'),
    dict(libelle="Salaires nets",                        type_charge='fixe', montant=Decimal('2725'),   unite='annuel'),
    dict(libelle="Cotisations URSSAF",                   type_charge='fixe', montant=Decimal('2266'),   unite='annuel'),
    # Sous-total fixe (hors amortissements) : 38 746 €

    # ── Marginal : nettoyage — coût par tenue, non partagé entre cohabitats ───
    dict(libelle="Entretien et nettoyage locaux",        type_charge='marginal', montant=Decimal('13650'), unite='annuel'),
    # Sous-total marginal : 13 650 €

    # ── Agapes / cuisine : auto-financés par le différentiel de tarif ─────────
    dict(libelle="Entretien cuisine",                    type_charge='agapes', montant=Decimal('2900'), unite='annuel'),
    dict(libelle="Maintenance cuisine",                  type_charge='agapes', montant=Decimal('726'),  unite='annuel'),
    # Sous-total agapes : 3 626 €
]

# Total exploitation = 51 800 + 38 746 + 13 650 + 3 626 = 107 822 €

# ── Poste additionnel : dotation aux amortissements ──────────────────────────
# Non-cash mais représente la consommation réelle du capital immobilisé.
# À inclure pour couvrir les coûts de fonctionnement complets.
POSTE_AMORTISSEMENTS = dict(
    libelle="Dotation aux amortissements",
    type_charge='fixe',
    montant=Decimal('3400'),
    unite='annuel',
)
# Avec amortissements : 107 822 + 3 400 = 111 222 €


class Command(BaseCommand):
    help = "Crée les PosteCharge pour la saison 2026 (Compte de résultat 31/08/2026)"

    def add_arguments(self, parser):
        parser.add_argument('--saison', type=int, default=2026,
                            help="Année de début de saison (défaut : 2026)")
        parser.add_argument('--force', action='store_true',
                            help="Supprime les postes existants avant de recréer")
        parser.add_argument('--sans-amortissements', action='store_true',
                            help="Exclut la dotation aux amortissements (3 400 €)")

    def handle(self, *args, **options):
        saison             = options['saison']
        force              = options['force']
        sans_amortissements = options['sans_amortissements']

        existants = PosteCharge.objects.filter(saison=saison).count()
        if existants and not force:
            self.stdout.write(self.style.WARNING(
                f"{existants} poste(s) déjà configuré(s) pour la saison {saison}-{saison+1}. "
                f"Utilisez --force pour réinitialiser."
            ))
            return

        if force and existants:
            PosteCharge.objects.filter(saison=saison).delete()
            self.stdout.write(f"  {existants} poste(s) existant(s) supprimé(s).")

        postes = list(POSTES_EXPLOITATION)
        if not sans_amortissements:
            postes.append(POSTE_AMORTISSEMENTS)

        total = Decimal('0')
        for p in postes:
            PosteCharge.objects.create(saison=saison, temple=None, actif=True, **p)
            total += p['montant']
            self.stdout.write(f"  ✓ {p['libelle']:50s} {p['type_charge']:12s} {p['montant']:>9} €")

        ref = "107 822 € exploitation" if sans_amortissements else "111 222 € (dont 3 400 € amortissements)"
        self.stdout.write(self.style.SUCCESS(
            f"\n{len(postes)} postes créés pour la saison {saison}-{saison+1}. "
            f"Total : {total:,.0f} € — référence compte de résultat 2026 : {ref}"
        ))
