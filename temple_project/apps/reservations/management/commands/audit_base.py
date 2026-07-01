from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from temple_project.apps.loges.models import Loge
from temple_project.apps.reservations.models import (
    RegleRecurrence, Reservation, ReservationSalle,
)


def _titre(s):
    return "\n" + "=" * 4 + " " + s + " " + "=" * max(4, 66 - len(s))


class Command(BaseCommand):
    help = "Audit de la base : contacts manquants, loges sans recurrence, doublons, anomalies."

    def add_arguments(self, parser):
        parser.add_argument('--details', action='store_true',
                            help="Liste tous les elements (sinon plafonne a 40)")

    def handle(self, *args, **o):
        LIM = None if o['details'] else 40

        def liste(qs_or_iter, fmt):
            items = list(qs_or_iter)
            for x in (items if LIM is None else items[:LIM]):
                self.stdout.write("   - " + fmt(x))
            if LIM is not None and len(items) > LIM:
                self.stdout.write(f"   ... (+{len(items) - LIM} autres, --details pour tout voir)")

        # ── Vue d'ensemble ────────────────────────────────────────────────────
        self.stdout.write(_titre("VUE D'ENSEMBLE"))
        par_statut = Counter(Loge.objects.values_list('statut', flat=True))
        self.stdout.write(f"Loges : {Loge.objects.count()} "
                          f"(active={par_statut.get('active',0)}, "
                          f"a_reconfirmer={par_statut.get('a_reconfirmer',0)}, "
                          f"inactive={par_statut.get('inactive',0)})")
        self.stdout.write(f"Regles de recurrence actives : {RegleRecurrence.objects.filter(actif=True).count()}")
        self.stdout.write(f"Reservations temple : {Reservation.objects.count()} "
                          f"(reguliere={Reservation.objects.filter(type_reservation='reguliere').count()}, "
                          f"exceptionnelle={Reservation.objects.filter(type_reservation='exceptionnelle').count()}, "
                          f"congres={Reservation.objects.filter(type_reservation='congres').count()})")
        self.stdout.write(f"Reservations de salle : {ReservationSalle.objects.count()}")

        actives = Loge.objects.exclude(statut='inactive')

        # ── Loges sans coordonnee de contact ─────────────────────────────────
        sans_contact = actives.filter(
            Q(email='') | Q(email__isnull=True)
        ).filter(telephone='').filter(nom_contact='')
        self.stdout.write(_titre(f"LOGES (actives) SANS CONTACT (ni email, ni tel, ni nom) : {sans_contact.count()}"))
        liste(sans_contact.order_by('nom'), lambda l: f"[{l.abreviation}] {l.nom} ({l.statut})")

        # ── Loges sans regle de recurrence ───────────────────────────────────
        sans_regle = actives.annotate(
            nr=Count('regles', filter=Q(regles__actif=True))).filter(nr=0)
        self.stdout.write(_titre(f"LOGES (actives) SANS REGLE DE RECURRENCE : {sans_regle.count()}"))
        liste(sans_regle.order_by('nom'), lambda l: f"[{l.abreviation}] {l.nom} ({l.statut})")

        # ── Loges sans aucune tenue ──────────────────────────────────────────
        sans_tenue = actives.annotate(
            nt=Count('reservations')).filter(nt=0)
        self.stdout.write(_titre(f"LOGES (actives) SANS AUCUNE TENUE TEMPLE : {sans_tenue.count()}"))
        liste(sans_tenue.order_by('nom'), lambda l: f"[{l.abreviation}] {l.nom}")

        # ── Doublons de loges (meme nom) ─────────────────────────────────────
        noms = Counter(n.strip().lower() for n in Loge.objects.values_list('nom', flat=True))
        dbl_nom = [n for n, c in noms.items() if c > 1]
        self.stdout.write(_titre(f"DOUBLONS DE LOGES (meme nom) : {len(dbl_nom)}"))
        for n in sorted(dbl_nom):
            grp = Loge.objects.filter(nom__iexact=n)
            self.stdout.write("   - " + " / ".join(f"pk{l.pk}[{l.abreviation}]{'*inactive' if l.statut=='inactive' else ''}" for l in grp) + f"  ({grp.first().nom})")

        # ── Doublons d'abreviation ───────────────────────────────────────────
        abr = Counter(a.strip().lower() for a in Loge.objects.values_list('abreviation', flat=True) if a and a.strip())
        dbl_abr = [a for a, c in abr.items() if c > 1]
        self.stdout.write(_titre(f"DOUBLONS D'ABREVIATION : {len(dbl_abr)}"))
        for a in sorted(dbl_abr):
            grp = Loge.objects.filter(abreviation__iexact=a)
            self.stdout.write("   - " + a + " : " + " / ".join(f"pk{l.pk} {l.nom}" for l in grp))

        # ── Doublons de regles ───────────────────────────────────────────────
        dbl_regles = (RegleRecurrence.objects
                      .values('loge__abreviation', 'temple__nom', 'jour_semaine', 'numero_semaine')
                      .annotate(n=Count('id')).filter(n__gt=1))
        self.stdout.write(_titre(f"DOUBLONS DE REGLES (meme loge/temple/jour/sem) : {len(dbl_regles)}"))
        liste(dbl_regles, lambda d: f"{d['loge__abreviation']} {d['temple__nom']} jour{d['jour_semaine']} sem{d['numero_semaine']} x{d['n']}")

        # ── Tenues recurrentes orphelines (sans regle) ───────────────────────
        orph = Reservation.objects.filter(type_reservation='reguliere', regle_source__isnull=True)
        self.stdout.write(_titre(f"TENUES 'reguliere' ORPHELINES (regle supprimee) : {orph.count()}"))
        parloge = Counter(orph.values_list('loge__abreviation', flat=True))
        liste(sorted(parloge.items(), key=lambda x: -x[1]), lambda kv: f"{kv[0]} : {kv[1]} tenue(s)")

        # ── Reservations sans loge ───────────────────────────────────────────
        self.stdout.write(_titre("RESERVATIONS SANS LOGE (loge vide)"))
        self.stdout.write(f"   temple : {Reservation.objects.filter(loge__isnull=True).count()} | "
                          f"salle : {ReservationSalle.objects.filter(loge__isnull=True).count()}")

        # ── Chevauchements le meme jour (loge dans 2 lieux) ──────────────────
        self.stdout.write(_titre("LOGES avec CHEVAUCHEMENT le meme jour (2 tenues qui se croisent)"))
        conflits = defaultdict(int)
        parjour = defaultdict(list)
        for r in Reservation.objects.filter(statut__in=['validee', 'attente']).select_related('loge'):
            if r.loge_id:
                parjour[(r.loge_id, r.date)].append(r)
        for (lid, d), items in parjour.items():
            if len(items) < 2:
                continue
            items.sort(key=lambda r: r.heure_debut)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    if items[i].heure_debut < items[j].heure_fin and items[i].heure_fin > items[j].heure_debut:
                        conflits[items[i].loge.abreviation] += 1
                        break
        liste(sorted(conflits.items(), key=lambda x: -x[1]), lambda kv: f"{kv[0]} : {kv[1]} jour(s) avec chevauchement")

        # ── Anomalies diverses ───────────────────────────────────────────────
        self.stdout.write(_titre("ANOMALIES DIVERSES"))
        h_ko = [r for r in RegleRecurrence.objects.all() if r.heure_fin <= r.heure_debut]
        self.stdout.write(f"Regles heure_fin <= heure_debut : {len(h_ko)}")
        for r in (h_ko if LIM is None else h_ko[:20]):
            self.stdout.write(f"   - {r.loge.abreviation} {r.temple.nom} {r.heure_debut}-{r.heure_fin}")
        reconf_avec_tenues = actives.filter(statut='a_reconfirmer').annotate(nt=Count('reservations')).filter(nt__gt=0)
        self.stdout.write(f"Loges 'a_reconfirmer' ayant quand meme des tenues : {reconf_avec_tenues.count()}")
        self.stdout.write("")
