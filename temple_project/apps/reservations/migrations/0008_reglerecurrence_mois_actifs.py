from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0007_reservationsalle_nombre_cabinets'),
    ]

    operations = [
        migrations.AddField(
            model_name='reglerecurrence',
            name='mois_actifs',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Mois actifs (1=Jan … 12=Déc). Laisser vide = tous les mois (sauf juillet-août).',
            ),
        ),
    ]
