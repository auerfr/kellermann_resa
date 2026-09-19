from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Aligns Facture and LigneFacture primary key to BigAutoField to match
    DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' in settings.
    Migration 0017 hand-wrote AutoField; this corrects the state delta.
    """

    dependencies = [
        ('administration', '0018_parametres_tarifs_externes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facture',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='lignefacture',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
