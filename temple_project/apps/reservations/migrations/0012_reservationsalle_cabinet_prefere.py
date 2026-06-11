from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0011_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservationsalle',
            name='cabinet_prefere',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reservations_preferees',
                to='reservations.sallereunion',
            ),
        ),
    ]
