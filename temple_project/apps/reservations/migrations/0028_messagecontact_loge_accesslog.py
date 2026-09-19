from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loges', '0001_initial'),
        ('reservations', '0027_messagecontact_emis'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagecontact',
            name='loge',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='messages_contact',
                to='loges.loge',
            ),
        ),
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[('portail', 'Accès portail loge'), ('calendrier', 'Connexion calendrier')],
                    db_index=True, max_length=20,
                )),
                ('loge', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='access_logs',
                    to='loges.loge',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': "Log d'accès",
                'verbose_name_plural': "Logs d'accès",
                'ordering': ['-created_at'],
            },
        ),
    ]
