from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0014_faq_demandes_modif'),
        ('reservations', '0029_demandemodificationreservation'),
    ]

    operations = [
        migrations.CreateModel(
            name='PosteCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('saison', models.PositiveIntegerField(help_text='Année de début de saison (ex : 2025 pour 2025-2026)')),
                ('libelle', models.CharField(max_length=100)),
                ('type_charge', models.CharField(choices=[('fixe', 'Charge fixe (loyer, assurance, maintenance…)'), ('mutualise', 'Variable mutualisée (chauffage, électricité de base…)'), ('marginal', 'Variable marginale (nettoyage, consommables…)')], max_length=20)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10)),
                ('unite', models.CharField(choices=[('annuel', 'Par an'), ('mensuel', 'Par mois'), ('par_heure', "Par heure d'occupation"), ('par_evenement', 'Par événement')], max_length=20)),
                ('actif', models.BooleanField(default=True)),
                ('temple', models.ForeignKey(blank=True, help_text='Laisser vide pour un poste commun à tous les temples', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='postes_charges', to='reservations.temple')),
            ],
            options={
                'verbose_name': 'Poste de charge',
                'verbose_name_plural': 'Postes de charges',
                'ordering': ['saison', 'temple', 'type_charge', 'libelle'],
            },
        ),
    ]
