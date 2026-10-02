from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0026_blocage_date_fin'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagecontact',
            name='emis',
            field=models.BooleanField(default=False, help_text="Message émis par l'admin (sortant)"),
        ),
    ]
