from django.db import migrations


def init_statut(apps, schema_editor):
    """Déduit le statut initial depuis le champ actif."""
    Loge = apps.get_model('loges', 'Loge')
    Loge.objects.filter(actif=False).update(statut='inactive')
    Loge.objects.filter(actif=True).update(statut='active')


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0008_loge_statut'),
    ]

    operations = [
        migrations.RunPython(init_statut, migrations.RunPython.noop),
    ]
