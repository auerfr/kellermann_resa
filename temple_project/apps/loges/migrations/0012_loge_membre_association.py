from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0011_loge_couverts_habituels'),
    ]

    operations = [
        migrations.AddField(
            model_name='loge',
            name='membre_association',
            field=models.BooleanField(
                default=True,
                help_text="Loge adhérente à l'association (cotisation annuelle). "
                          "Décocher pour les occupants occasionnels / externes qui ne paient qu'à la tenue.",
            ),
        ),
    ]
