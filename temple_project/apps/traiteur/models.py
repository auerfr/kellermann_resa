from django.db import models
from temple_project.apps.loges.models import Loge


class NotificationCouverts(models.Model):
    """Notification envoyée par un membre pour signaler un changement de couverts."""

    STATUT_CHOICES = [
        ("non_lu", "Non lue"),
        ("lu",     "Lue"),
    ]

    loge            = models.ForeignKey(
        Loge, on_delete=models.CASCADE, related_name="notifications_couverts"
    )
    date_tenue      = models.DateField()
    nombre_couverts = models.PositiveIntegerField()
    commentaire     = models.TextField(blank=True)
    email_contact   = models.EmailField()
    statut          = models.CharField(max_length=10, choices=STATUT_CHOICES, default="non_lu")
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification couverts"
        verbose_name_plural = "Notifications couverts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.loge} – {self.date_tenue} – {self.nombre_couverts} couverts [{self.get_statut_display()}]"
