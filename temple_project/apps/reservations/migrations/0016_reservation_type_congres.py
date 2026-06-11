from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0015_data_salle_humide_groupe_traiteur"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="type_reservation",
            field=models.CharField(
                choices=[
                    ("reguliere",     "Régulière"),
                    ("exceptionnelle","Exceptionnelle"),
                    ("congres",       "Congrès / Session régionale"),
                ],
                default="reguliere",
                max_length=20,
            ),
        ),
    ]
