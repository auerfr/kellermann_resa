from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0011_parametres_tarif_membre_hg_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FAQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('connexion', 'Page de connexion (mini FAQ)'), ('membres', 'FAQ membres connectés'), ('traiteur', 'FAQ traiteur')], db_index=True, max_length=20)),
                ('section', models.CharField(blank=True, help_text='Titre de section (ex: Réservations, Calendrier…)', max_length=100)),
                ('question', models.CharField(max_length=400)),
                ('reponse', models.TextField()),
                ('ordre', models.PositiveIntegerField(default=0, help_text="Ordre d'affichage dans la catégorie")),
                ('actif', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'FAQ',
                'verbose_name_plural': 'FAQ',
                'ordering': ['categorie', 'ordre', 'pk'],
            },
        ),
    ]
