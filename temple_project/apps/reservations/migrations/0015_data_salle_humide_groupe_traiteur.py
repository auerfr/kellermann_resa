"""
Data migration :
  - Crée la SalleReunion "Salle Humide" (type=agapes, capacite=60) si elle n'existe pas.
  - Crée le groupe Django "Traiteur" si il n'existe pas.
"""
from django.db import migrations


def ajouter_salle_humide_et_groupe(apps, schema_editor):
    SalleReunion = apps.get_model("reservations", "SalleReunion")
    SalleReunion.objects.get_or_create(
        nom="Salle Humide",
        defaults={"type_salle": "agapes", "capacite": 60, "actif": True},
    )

    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Traiteur")


def supprimer_salle_humide_et_groupe(apps, schema_editor):
    SalleReunion = apps.get_model("reservations", "SalleReunion")
    SalleReunion.objects.filter(nom="Salle Humide", type_salle="agapes").delete()

    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Traiteur").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0014_blocagecreneaux"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            ajouter_salle_humide_et_groupe,
            supprimer_salle_humide_et_groupe,
        ),
    ]
