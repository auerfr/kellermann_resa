from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0005_rite_choices_rf_reaa'),
    ]

    operations = [
        migrations.AddField(
            model_name='loge',
            name='rite_precision',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
