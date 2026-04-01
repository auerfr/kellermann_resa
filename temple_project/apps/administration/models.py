from django.db import models


class Parametres(models.Model):
    mot_de_passe_annuel = models.CharField(max_length=100, default="KELLERMANN2026")
    email_admin = models.EmailField()
    email_from = models.EmailField(default="noreply@temple-reservations.fr")
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_tls = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Paramètres"
        verbose_name_plural = "Paramètres"

    @classmethod
    def get_instance(cls):
        instance, created = cls.objects.get_or_create(pk=1, defaults={})
        return instance