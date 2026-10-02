"""
Peuple les PosteCharge pour la saison 2026 à partir du Budget AG 2026.

Usage :
    python manage.py init_postes_2026
    python manage.py init_postes_2026 --saison 2025   # pour 2025-2026 à la place
    python manage.py init_postes_2026 --force          # réinitialise si déjà existants
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from temple_project.apps.administration.models import PosteCharge


POSTES = [
    # ── Mutualisés : énergie partagée entre tous les occupants du jour ──────
    # (divisés par le nb d'occupants → économie d'échelle réelle)
    dict(libelle="Eau",                              type_charge='mutualise', montant=Decimal('1000'),  unite='annuel'),
    dict(libelle="Électricité",                      type_charge='mutualise', montant=Decimal('22000'), unite='annuel'),
    dict(libelle="Gaz",                              type_charge='mutualise', montant=Decimal('30000'), unite='annuel'),
    dict(libelle="Maintenance chauffage (50 %)",     type_charge='mutualise', montant=Decimal('5000'),  unite='annuel'),

    # ── Fixes : charges de structure, réparties sur l'ensemble des tenues ──
    dict(libelle="Petit équipement (temples)",       type_charge='fixe', montant=Decimal('1500'),  unite='annuel'),
    dict(libelle="Entretien et réparations (intérieur)",  type_charge='fixe', montant=Decimal('5000'),  unite='annuel'),
    dict(libelle="Entretien et réparations (extérieur)",  type_charge='fixe', montant=Decimal('2500'),  unite='annuel'),
    dict(libelle="Entretien et réparations (temples)",    type_charge='fixe', montant=Decimal('2000'),  unite='annuel'),
    dict(libelle="Maintenance ascenseur",            type_charge='fixe', montant=Decimal('350'),   unite='annuel'),
    dict(libelle="Contrôle incendie et autres",      type_charge='fixe', montant=Decimal('1070'),  unite='annuel'),
    dict(libelle="Assurance multirisques",           type_charge='fixe', montant=Decimal('1100'),  unite='annuel'),
    dict(libelle="Assurance risques financiers",     type_charge='fixe', montant=Decimal('500'),   unite='annuel'),
    dict(libelle="Abonnement Orange + affranchissements", type_charge='fixe', montant=Decimal('650'), unite='annuel'),
    dict(libelle="Services bancaires",               type_charge='fixe', montant=Decimal('280'),   unite='annuel'),
    dict(libelle="Taxe ordures ménagères",           type_charge='fixe', montant=Decimal('1000'),  unite='annuel'),
    dict(libelle="Salaires nets",                    type_charge='fixe', montant=Decimal('3442'),  unite='annuel'),
    dict(libelle="Cotisations URSSAF",               type_charge='fixe', montant=Decimal('3724'),  unite='annuel'),

    # ── Marginal : nettoyage à la tenue (coût par tenue, non partagé) ───────
    dict(libelle="Prestation nettoyage externe",     type_charge='marginal', montant=Decimal('11880'), unite='annuel'),

    # ── Agapes / cuisine : uniquement si la loge demande la cuisine ─────────
    # (auto-financés via le différentiel de tarif avec/sans agapes)
    dict(libelle="Entretien cuisine",                type_charge='agapes', montant=Decimal('2500'), unite='annuel'),
    dict(libelle="Maintenance cuisine",              type_charge='agapes', montant=Decimal('700'),  unite='annuel'),
]

# Vérification : 58 000 + 23 116 + 11 880 + 3 200 = 96 196 €
# mutualise=58 000, fixe=23 116 (=1500+5000+2500+2000+350+1070+1100+500+650+280+1000+3442+3724),
# marginal=11 880, agapes=3 200


class Command(BaseCommand):
    help = "Crée les PosteCharge pour la saison 2026 à partir du Budget AG 2026"

    def add_arguments(self, parser):
        parser.add_argument('--saison', type=int, default=2026,
                            help="Année de début de saison (défaut : 2026)")
        parser.add_argument('--force', action='store_true',
                            help="Supprime les postes existants avant de recréer")

    def handle(self, *args, **options):
        saison = options['saison']
        force  = options['force']

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

        total = Decimal('0')
        for p in POSTES:
            PosteCharge.objects.create(
                saison=saison,
                temple=None,
                actif=True,
                **p,
            )
            total += p['montant']
            self.stdout.write(f"  ✓ {p['libelle']:50s} {p['type_charge']:12s} {p['montant']:>8} €")

        self.stdout.write(self.style.SUCCESS(
            f"\n{len(POSTES)} postes créés pour la saison {saison}-{saison+1}. "
            f"Total : {total:,.0f} € (budget AG 2026 : 96 196 €)"
        ))
