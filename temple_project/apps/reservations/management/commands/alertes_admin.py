from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Envoie un email de synthese qualite a l'administrateur (conflits, "
            "tenues orphelines, doublons, loges sans email/recurrence, a "
            "reconfirmer). A planifier via une tache cron (ex: chaque lundi).")

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help="Envoyer meme s'il n'y a rien a signaler.")

    def handle(self, *args, **o):
        from django.db.models import Count, Q
        from temple_project.apps.administration.views import _scan_conflits
        from temple_project.apps.administration.email_utils import (
            send_mail_kellermann, get_email_admin)
        from temple_project.apps.loges.models import Loge
        from temple_project.apps.reservations.models import (
            Reservation, RegleRecurrence)

        actives = Loge.objects.exclude(statut='inactive')
        lignes = [
            ('Catapultages (conflits de creneau)', len(_scan_conflits())),
            ('Tenues orphelines (sans loge)',
             Reservation.objects.filter(loge__isnull=True, type_reservation='reguliere').count()),
            ('Doublons de regles',
             RegleRecurrence.objects.values('loge', 'temple', 'jour_semaine', 'numero_semaine')
             .annotate(n=Count('id')).filter(n__gt=1).count()),
            ('Loges sans email',
             actives.filter(Q(email='') | Q(email__isnull=True)).count()),
            ('Loges sans recurrence',
             actives.annotate(nr=Count('regles', filter=Q(regles__actif=True))).filter(nr=0).count()),
            ('Loges a reconfirmer', Loge.objects.filter(statut='a_reconfirmer').count()),
        ]
        total = sum(v for _, v in lignes)
        if total == 0 and not o['force']:
            self.stdout.write("Rien a signaler — pas d'email.")
            return

        corps = (
            "Bonjour,\n\nSynthese de la sante des donnees Kellermann :\n\n"
            + "\n".join(f"  - {lbl} : {v}" for lbl, v in lignes)
            + "\n\nDetail et actions : rubrique Administration > Sante des donnees.\n\n"
            "Bien fraternellement,\nLes Temples Kellermann"
        )
        dest = get_email_admin()
        send_mail_kellermann(
            subject=f"[Kellermann] Alertes qualite — {total} point(s) a regarder",
            message=corps, recipient_list=[dest])
        self.stdout.write(self.style.SUCCESS(f"Email envoye a {dest} ({total} point(s))."))
