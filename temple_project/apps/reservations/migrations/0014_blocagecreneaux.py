from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0013_demandeaccesportail"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BlocageCreneaux",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("heure_debut", models.TimeField()),
                ("heure_fin", models.TimeField()),
                ("motif", models.CharField(max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "salles",
                    models.ManyToManyField(
                        blank=True,
                        related_name="blocages",
                        to="reservations.sallereunion",
                    ),
                ),
                (
                    "temples",
                    models.ManyToManyField(
                        blank=True,
                        related_name="blocages",
                        to="reservations.temple",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blocages_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Blocage de créneau",
                "verbose_name_plural": "Blocages de créneaux",
                "ordering": ["date", "heure_debut"],
            },
        ),
    ]
