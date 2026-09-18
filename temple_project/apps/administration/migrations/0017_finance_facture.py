from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0016_postecharge_choices_agapes_salle'),
        ('loges', '0001_initial'),
        ('reservations', '0001_initial'),
    ]

    operations = [
        # Flag d'activation du module finance dans Parametres
        migrations.AddField(
            model_name='parametres',
            name='module_finance_actif',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Active le module de facturation annuelle par loge "
                    "(factures cristallisées, PDF, envoi email). "
                    "À activer après validation du modèle avec le trésorier."
                ),
            ),
        ),

        # Modèle Facture
        migrations.CreateModel(
            name='Facture',
            fields=[
                ('id',            models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('saison',        models.PositiveIntegerField(help_text='Année de début de saison (ex : 2025 pour 2025-2026)')),
                ('numero',        models.CharField(blank=True, db_index=True, max_length=30,
                                                   help_text='Numéro définitif généré à l\'émission (ex: KELL-2026-001)')),
                ('date_emission', models.DateField(blank=True, null=True)),
                ('date_echeance', models.DateField(blank=True, null=True)),
                ('statut',        models.CharField(choices=[
                                      ('brouillon', 'Brouillon'),
                                      ('emise',     'Émise'),
                                      ('payee',     'Payée'),
                                      ('annulee',   'Annulée'),
                                  ], db_index=True, default='brouillon', max_length=20)),
                ('notes',         models.TextField(blank=True,
                                                   help_text='Notes libres (exonération partielle, accord trésorier…)')),
                ('total_ht',      models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('updated_at',    models.DateTimeField(auto_now=True)),
                ('loge',          models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                    related_name='factures', to='loges.loge')),
            ],
            options={
                'verbose_name':        'Facture',
                'verbose_name_plural': 'Factures',
                'ordering':            ['-saison', 'loge__nom'],
            },
        ),
        migrations.AddConstraint(
            model_name='facture',
            constraint=models.UniqueConstraint(fields=['loge', 'saison'], name='finance_facture_loge_saison_uniq'),
        ),
        migrations.AddIndex(
            model_name='facture',
            index=models.Index(fields=['-saison', 'statut'], name='finance_facture_saison_idx'),
        ),

        # Modèle LigneFacture
        migrations.CreateModel(
            name='LigneFacture',
            fields=[
                ('id',               models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('type_ligne',       models.CharField(choices=[
                                         ('cotisation_lb',       'Cotisation membre — loge bleue'),
                                         ('cotisation_hg',       'Cotisation membre — haut grade'),
                                         ('infrastructure_fixe', 'Part infrastructure fixe'),
                                         ('infrastructure_mut',  'Part infrastructure mutualisée'),
                                         ('infrastructure_marg', 'Part infrastructure marginale'),
                                         ('agapes',              'Usage cuisine / agapes'),
                                         ('salle',               'Usage salle de réunion'),
                                         ('tenue_exc',           'Tenue exceptionnelle'),
                                         ('autre',               'Autre'),
                                     ], max_length=30)),
                ('libelle',          models.CharField(max_length=200)),
                ('quantite',         models.DecimalField(decimal_places=2, default=Decimal('1'), max_digits=8)),
                ('unite',            models.CharField(blank=True, max_length=50)),
                ('montant_unitaire', models.DecimalField(decimal_places=2, max_digits=10)),
                ('montant_total',    models.DecimalField(decimal_places=2, max_digits=10)),
                ('facturable',       models.BooleanField(default=True,
                                                         help_text='Décocher pour exclure cette ligne sans la supprimer')),
                ('ordre',            models.PositiveIntegerField(default=0)),
                ('facture',          models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                       related_name='lignes', to='administration.facture')),
                ('reservation',      models.ForeignKey(blank=True, null=True,
                                                       on_delete=django.db.models.deletion.SET_NULL,
                                                       related_name='lignes_facture',
                                                       to='reservations.reservation')),
                ('reservation_salle', models.ForeignKey(blank=True, null=True,
                                                        on_delete=django.db.models.deletion.SET_NULL,
                                                        related_name='lignes_facture',
                                                        to='reservations.reservationsalle')),
            ],
            options={
                'verbose_name':        'Ligne de facture',
                'verbose_name_plural': 'Lignes de facture',
                'ordering':            ['ordre', 'type_ligne'],
            },
        ),
    ]
