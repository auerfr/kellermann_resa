from datetime import date

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Audit de capacite : creneaux-soir recurrents libres (combien de loges "
            "en plus) et taux d'occupation calendaire du soir par temple.")

    def add_arguments(self, parser):
        parser.add_argument('--annee', type=int,
                            help="Annee de debut de saison (defaut : saison en cours)")

    def handle(self, *args, **o):
        from temple_project.apps.administration.views import _audit_capacite

        annee = o.get('annee') or (date.today().year if date.today().month >= 9
                                   else date.today().year - 1)
        c = _audit_capacite(annee)
        h, cal = c['homes'], c['calendrier']

        def titre(s):
            self.stdout.write("\n" + "=" * 3 + " " + s + " " + "=" * max(3, 60 - len(s)))

        titre(f"AUDIT CAPACITE - saison {annee}/{annee+1} ({c['nb_temples']} temples)")

        titre("HOMES RECURRENTS DU SOIR (temple x jour lun-sam x position 1-4)")
        self.stdout.write(f"Lun-Sam : {h['total']} creneaux, {h['occ']} occupes, "
                          f"{h['libres']} LIBRES")
        self.stdout.write(f"Lun-Ven (coeur) : {h['total_lv']} creneaux, {h['occ_lv']} occupes, "
                          f"{h['libres_lv']} LIBRES")
        self.stdout.write(self.style.SUCCESS(
            f"=> ~{h['libres_lv']} loges supplementaires pourraient avoir un creneau "
            f"recurrent du soir en semaine (jusqu'a ~{h['libres']} avec le samedi)."))
        self.stdout.write("Par temple (lun-sam) : total / occ / libres")
        for pt in h['par_temple']:
            self.stdout.write(f"   {pt['temple']:<22} {pt['total']:>3} / {pt['occ']:>3} / {pt['libres']:>3}")
        self.stdout.write("Creneaux-soir LIBRES par jour : "
                          + ", ".join(f"{j} {v}" for j, v in h['libres_par_jour'].items()))

        titre(f"OCCUPATION CALENDAIRE DU SOIR ({cal['dates_par_temple']} soirees/temple)")
        self.stdout.write("Temple : soirees / occupees / libres (taux libre)")
        for x in cal['par_temple']:
            self.stdout.write(f"   {x['temple']:<22} {x['dates']:>3} / {x['occ']:>3} / "
                              f"{x['libres']:>3}  ({100 - x['taux']:.0f}% libre)")
        self.stdout.write(f"GLOBAL : {cal['total_dates']} soirees, {cal['total_occ']} occupees, "
                          f"{cal['total_libres']} libres ({100 - cal['taux']:.0f}% libre).")

        we = c['weekend']
        titre("WEEK-END MATIN & APRES-MIDI (samedi + dimanche)")
        wh = we['homes']
        self.stdout.write(f"Homes recurrents : {wh['total']} creneaux, {wh['occ']} occupes, "
                          f"{wh['libres']} LIBRES")
        self.stdout.write(self.style.SUCCESS(
            f"=> ~{wh['libres']} creneaux week-end matin/apres-midi disponibles."))
        self.stdout.write("Par case (jour / partie) : total / occ / libres")
        for cs in wh['par_case']:
            self.stdout.write(f"   {cs['jour']:<9} {cs['partie']:<11} "
                              f"{cs['total']:>3} / {cs['occ']:>3} / {cs['libres']:>3}")
        self.stdout.write("Occupation calendaire (soirees=creneaux temple x date) :")
        for cs in we['calendrier']['par_case']:
            self.stdout.write(f"   {cs['jour']:<9} {cs['partie']:<11} "
                              f"{cs['dates']:>4} slots, {cs['occ']:>3} occ, {cs['libres']:>4} libres "
                              f"({100 - cs['taux']:.0f}% libre)")
        self.stdout.write("")
