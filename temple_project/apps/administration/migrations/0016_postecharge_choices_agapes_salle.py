from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0015_poste_charge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='postecharge',
            name='type_charge',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('fixe',      'Charge fixe (loyer, assurance, maintenance…)'),
                    ('mutualise', 'Variable mutualis\xe9e (chauffage, \xe9lectricit\xe9 de base…)'),
                    ('marginal',  'Variable marginale (nettoyage, consommables…)'),
                    ('agapes',    'Usage cuisine / agapes (uniquement si agapes demand\xe9es)'),
                    ('salle',     'Salle de r\xe9union / cabinet (par occupation de salle)'),
                ],
            ),
        ),
    ]
