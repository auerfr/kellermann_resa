import re
import unicodedata

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import ReservationSalle


def _norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', s.lower())


def match_loge_par_organisation(org):
    """Retrouve la loge correspondant à un nom d'organisation saisi en texte
    libre : par abréviation entre parenthèses « (ABREV) », sinon par nom
    normalisé (accents/casse/ponctuation ignorés). Renvoie la loge ou None."""
    from temple_project.apps.loges.models import Loge
    if not org:
        return None
    m = re.search(r'\(([^)]+)\)\s*$', org)
    if m:
        loge = Loge.objects.filter(abreviation__iexact=m.group(1).strip()).first()
        if loge:
            return loge
    n = _norm(re.sub(r'\([^)]*\)', '', org))
    if not n:
        return None
    for loge in Loge.objects.all():
        ln = _norm(loge.nom)
        if ln and (n == ln or n.startswith(ln) or ln.startswith(n)):
            return loge
    return None


@receiver(pre_save, sender=ReservationSalle)
def relier_loge_reservation_salle(sender, instance, **kwargs):
    """Si une réservation de salle n'a pas de loge liée mais un nom
    d'organisation qui correspond à une loge, on la relie automatiquement
    (pour qu'elle apparaisse sur le portail et la fiche de la loge)."""
    if instance.loge_id is None and instance.organisation:
        loge = match_loge_par_organisation(instance.organisation)
        if loge:
            instance.loge = loge
