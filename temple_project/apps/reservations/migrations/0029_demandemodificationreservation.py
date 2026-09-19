from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0028_messagecontact_loge_accesslog'),
        ('loges', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeModificationReservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_demande', models.CharField(
                    choices=[('annulation', 'Annulation'), ('deplacement', 'Déplacement de date')],
                    max_length=15,
                )),
                ('nouvelle_date', models.DateField(blank=True, null=True)),
                ('motif', models.TextField(blank=True)),
                ('statut', models.CharField(
                    choices=[('attente', 'En attente'), ('acceptee', 'Acceptée'), ('refusee', 'Refusée')],
                    default='attente',
                    max_length=10,
                )),
                ('commentaire_admin', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('loge', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='demandes_modif',
                    to='loges.loge',
                )),
                ('reservation', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='demandes_modif',
                    to='reservations.reservation',
                )),
                ('reservation_salle', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='demandes_modif',
                    to='reservations.reservationsalle',
                )),
            ],
            options={
                'verbose_name': 'Demande de modification',
                'verbose_name_plural': 'Demandes de modification',
                'ordering': ['-created_at'],
            },
        ),
    ]
