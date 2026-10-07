from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0017_finance_facture'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametres',
            name='tarif_loge_occasionnelle',
            field=models.DecimalField(
                max_digits=8, decimal_places=2, default=Decimal('150'),
                help_text="Loge externe ou occasionnelle (invitée, de passage), par tenue (€)"),
        ),
        migrations.AddField(
            model_name='parametres',
            name='tarif_hg_externe',
            field=models.DecimalField(
                max_digits=8, decimal_places=2, default=Decimal('100'),
                help_text="Atelier haut grade externe / inter-obédientiel, par tenue (€)"),
        ),
        migrations.AddField(
            model_name='parametres',
            name='tarif_hg_interne_non_regulier',
            field=models.DecimalField(
                max_digits=8, decimal_places=2, default=Decimal('50'),
                help_text="Atelier HG interne non régulier (2-3 tenues/an, pas de règle récurrente), par tenue (€)"),
        ),
    ]
