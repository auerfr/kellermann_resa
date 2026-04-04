import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0001_initial'),
        ('reservations', '0008_reglerecurrence_mois_actifs'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeRegleRecurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('jour_semaine', models.PositiveSmallIntegerField(choices=[(0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche')])),
                ('numero_semaine', models.SmallIntegerField(choices=[(1, '1re semaine'), (2, '2e semaine'), (3, '3e semaine'), (4, '4e semaine'), (-1, 'Dernière semaine')])),
                ('heure_debut', models.TimeField()),
                ('heure_fin', models.TimeField()),
                ('mois_actifs', models.JSONField(blank=True, default=list)),
                ('nom_demandeur', models.CharField(max_length=100)),
                ('email_demandeur', models.EmailField()),
                ('commentaire', models.TextField(blank=True)),
                ('commentaire_admin', models.TextField(blank=True)),
                ('statut', models.CharField(choices=[('attente', 'En attente'), ('validee', 'Validée'), ('refusee', 'Refusée')], default='attente', max_length=10)),
                ('date_demande', models.DateTimeField(auto_now_add=True)),
                ('loge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_regle', to='loges.loge')),
                ('temple', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='reservations.temple')),
                ('regle_creee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='demande_source', to='reservations.reglerecurrence')),
            ],
            options={
                'verbose_name': 'Demande de règle de récurrence',
                'verbose_name_plural': 'Demandes de règles de récurrence',
                'ordering': ['-date_demande'],
            },
        ),
    ]
