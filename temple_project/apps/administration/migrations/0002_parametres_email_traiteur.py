from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("administration", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametres",
            name="email_traiteur",
            field=models.EmailField(
                blank=True,
                default="",
                help_text="Copie automatique pour le traiteur sur agapes/banquets",
            ),
            preserve_default=False,
        ),
    ]
