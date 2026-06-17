from datetime import date
from decimal import Decimal

from django.db import migrations


def init_tarifs(apps, schema_editor):
    """Initialise les tarifs et la date d'entrée en vigueur si non renseignés."""
    Parametres = apps.get_model('administration', 'Parametres')
    p = Parametres.objects.first()
    if not p:
        return
    changed = False
    if not p.tarif_exc_sans_agapes:
        p.tarif_exc_sans_agapes = Decimal('100'); changed = True
    if not p.tarif_exc_avec_agapes:
        p.tarif_exc_avec_agapes = Decimal('200'); changed = True
    if not p.tarif_congres_jour:
        p.tarif_congres_jour = Decimal('300'); changed = True
    if not p.tarif_date_effet:
        p.tarif_date_effet = date(2026, 6, 12); changed = True
    if changed:
        p.save()


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0007_parametres_tarif_date_effet'),
    ]

    operations = [
        migrations.RunPython(init_tarifs, migrations.RunPython.noop),
    ]
