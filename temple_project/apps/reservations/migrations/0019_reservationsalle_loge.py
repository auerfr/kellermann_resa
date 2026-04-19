from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0006_loge_rite_precision'),
        ('reservations', '0018_avis_attente_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservationsalle',
            name='loge',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reservations_salle',
                to='loges.loge',
            ),
        ),
    ]
