from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Loge


@receiver(pre_delete, sender=Loge)
def supprimer_donnees_loge(sender, instance, **kwargs):
    """Quand une loge est supprimee (admin Django ou code), on supprime aussi
    ses tenues et reservations de salle. Sans ca, elles restent 'orphelines'
    (loge=NULL, on_delete=SET_NULL) et continuent d'apparaitre sur le calendrier.
    Les regles de recurrence sont deja supprimees en CASCADE."""
    from temple_project.apps.reservations.models import Reservation, ReservationSalle
    Reservation.objects.filter(loge=instance).delete()
    ReservationSalle.objects.filter(loge=instance).delete()
