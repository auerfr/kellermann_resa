from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0003_journalevenement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='journalevenement',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='journalevenement',
            name='type_evenement',
            field=models.CharField(
                choices=[
                    ('validation_reservation',       'Validation réservation'),
                    ('refus_reservation',            'Refus réservation'),
                    ('modification_reservation',     'Modification réservation'),
                    ('soumission_portail_loge',      'Soumission portail loge'),
                    ('ouverture_validation_saison',  'Ouverture validation saison'),
                    ('envoi_emails_saison',          'Envoi emails saison'),
                    ('soumission_validation_loge',   'Soumission validation loge'),
                    ('import_excel',                 'Import Excel'),
                    ('backup_base',                  'Backup base de données'),
                    ('creation_reservation_directe', 'Création réservation directe'),
                    ('creation_acces_portail',       'Création accès portail'),
                    ('envoi_lien_portail',           'Envoi lien portail'),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
    ]
