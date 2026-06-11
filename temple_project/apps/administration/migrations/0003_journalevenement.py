import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("administration", "0002_parametres_email_traiteur"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JournalEvenement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("date_heure", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evenements_journal",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "type_evenement",
                    models.CharField(
                        choices=[
                            ("validation_reservation",       "Validation réservation"),
                            ("refus_reservation",            "Refus réservation"),
                            ("modification_reservation",     "Modification réservation"),
                            ("soumission_portail_loge",      "Soumission portail loge"),
                            ("ouverture_validation_saison",  "Ouverture validation saison"),
                            ("envoi_emails_saison",          "Envoi emails saison"),
                            ("soumission_validation_loge",   "Soumission validation loge"),
                            ("import_excel",                 "Import Excel"),
                            ("backup_base",                  "Backup base de données"),
                            ("creation_reservation_directe", "Création réservation directe"),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                ("description", models.TextField()),
                (
                    "objet_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("reservation",       "Réservation"),
                            ("reservation_salle", "Réservation salle"),
                            ("loge",              "Loge"),
                            ("validation_saison", "Validation de saison"),
                            ("systeme",           "Système"),
                        ],
                        max_length=30,
                    ),
                ),
                ("objet_id",    models.PositiveIntegerField(blank=True, null=True)),
                ("objet_label", models.CharField(blank=True, max_length=300)),
                ("ip_address",  models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                "verbose_name":        "Événement journal",
                "verbose_name_plural": "Journal des événements",
                "ordering":            ["-date_heure"],
            },
        ),
        migrations.AddIndex(
            model_name="journalevenement",
            index=models.Index(fields=["-date_heure"], name="admin_journal_date_idx"),
        ),
        migrations.AddIndex(
            model_name="journalevenement",
            index=models.Index(fields=["type_evenement"], name="admin_journal_type_idx"),
        ),
        migrations.AddIndex(
            model_name="journalevenement",
            index=models.Index(fields=["objet_type", "objet_id"], name="admin_journal_objet_idx"),
        ),
    ]
