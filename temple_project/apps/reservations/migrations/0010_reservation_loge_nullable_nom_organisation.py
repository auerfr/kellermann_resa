from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0001_initial'),
        ('reservations', '0009_demanderecurrence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservation',
            name='loge',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reservations',
                to='loges.loge',
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='nom_organisation',
            field=models.CharField(
                blank=True,
                max_length=200,
                help_text="Si la loge n'est pas dans la liste, saisissez son nom ici.",
            ),
        ),
    ]
