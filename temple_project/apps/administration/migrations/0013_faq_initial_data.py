from django.db import migrations

FAQ_INITIAL = [
    # ── Page de connexion (mini FAQ) ──────────────────────────────────────────
    {"categorie": "connexion", "section": "", "ordre": 1,
     "question": "Je n'ai pas le code d'accès annuel",
     "reponse": "Le code est distribué en début de saison par votre vénérable ou l'officier responsable. Si vous ne l'avez pas reçu, contactez directement votre loge."},
    {"categorie": "connexion", "section": "", "ordre": 2,
     "question": "Comment accéder à mon espace loge personnalisé ?",
     "reponse": "Cliquez sur « Recevoir mon lien d'espace loge » ci-dessous. Votre loge recevra un lien unique et sécurisé donnant accès au portail loge (calendrier de votre loge, abonnement calendrier, etc.)."},
    {"categorie": "connexion", "section": "", "ordre": 3,
     "question": "Qui peut utiliser cet outil ?",
     "reponse": "Cet outil est réservé aux membres et officiers des loges affiliées aux Temples Kellermann. Pour toute question, utilisez le formulaire de contact disponible sur la page d'accueil."},

    # ── FAQ membres — section Réservations ───────────────────────────────────
    {"categorie": "membres", "section": "Réservations", "ordre": 10,
     "question": "Comment réserver un temple ?",
     "reponse": "Dans le menu « Faire une demande » → « Réserver un temple ». Remplissez le formulaire (date, temple, heure, type de tenue, nombre de frères). La demande est soumise à validation par l'administrateur."},
    {"categorie": "membres", "section": "Réservations", "ordre": 11,
     "question": "Comment réserver une salle de réunion ?",
     "reponse": "Menu « Faire une demande » → « Réserver une salle ». Indiquez la date, la salle souhaitée, l'horaire et l'objet de la réunion. Les salles disponibles apparaissent automatiquement selon les disponibilités."},
    {"categorie": "membres", "section": "Réservations", "ordre": 12,
     "question": "Comment réserver des cabinets de réflexion ?",
     "reponse": "Menu « Faire une demande » → « Réserver des cabinets ». Les cabinets peuvent être réservés en complément d'une tenue pour les initiations et élévations."},
    {"categorie": "membres", "section": "Réservations", "ordre": 13,
     "question": "Que se passe-t-il après ma demande ?",
     "reponse": "Votre demande est envoyée à l'administrateur qui la valide (ou la refuse avec un motif). Vous recevez un email de confirmation à l'adresse indiquée. La réservation apparaît alors sur le calendrier général."},
    {"categorie": "membres", "section": "Réservations", "ordre": 14,
     "question": "Comment modifier ou annuler une réservation ?",
     "reponse": "Les modifications et annulations passent par l'administrateur. Utilisez le formulaire de contact (menu « Contact ») en précisant la date, le temple et la loge concernés. L'admin peut également effectuer les modifications directement."},
    {"categorie": "membres", "section": "Réservations", "ordre": 15,
     "question": "Qu'est-ce qu'une réservation récurrente ?",
     "reponse": "Une récurrence permet de planifier l'ensemble de vos tenues régulières sur la saison en une seule demande. Menu « Faire une demande » → « Demander une récurrence ». L'administrateur valide l'ensemble du cycle et les dates s'ajoutent automatiquement au calendrier."},
    {"categorie": "membres", "section": "Réservations", "ordre": 16,
     "question": "Comment réserver pour un banquet d'ordre (agapes) ?",
     "reponse": "Menu « Faire une demande » → « Banquet d'ordre ». Précisez le nombre de couverts. Une notification est automatiquement envoyée au traiteur. Vous pouvez aussi notifier le traiteur séparément via « Notifier le traiteur »."},

    # ── FAQ membres — section Calendrier ─────────────────────────────────────
    {"categorie": "membres", "section": "Calendrier", "ordre": 20,
     "question": "Comment vérifier la disponibilité d'une date ?",
     "reponse": "Sur la page Calendrier, cliquez sur l'icône 🔍 (Dispo) pour ouvrir l'outil de vérification. Sélectionnez une date et un temple pour voir instantanément si le créneau est libre."},
    {"categorie": "membres", "section": "Calendrier", "ordre": 21,
     "question": "Comment s'abonner au calendrier (Google, iPhone, Outlook…) ?",
     "reponse": "Sur la page Calendrier, cliquez sur le bouton 📅 ICS. Copiez le lien ou cliquez directement sur le bouton de votre application. Pour Google Agenda : Autres agendas → Depuis l'URL → coller le lien. Le calendrier se met à jour automatiquement (délai de synchronisation : jusqu'à 24h pour Google)."},
    {"categorie": "membres", "section": "Calendrier", "ordre": 22,
     "question": "Comment exporter le planning en PDF ?",
     "reponse": "Sur la page Calendrier, cliquez sur 📄 PDF. Choisissez la période (mois, saison Sep→Jun ou dates personnalisées), filtrez éventuellement par temple, puis cliquez « Générer le PDF »."},

    # ── FAQ membres — section Portail loge ───────────────────────────────────
    {"categorie": "membres", "section": "Portail loge", "ordre": 30,
     "question": "Qu'est-ce que le portail loge ?",
     "reponse": "Le portail loge est un espace personnalisé et sécurisé pour votre loge. Il affiche uniquement vos réservations (passées et futures), vos prochaines tenues, et donne accès à un abonnement calendrier limité à votre loge."},
    {"categorie": "membres", "section": "Portail loge", "ordre": 31,
     "question": "Comment accéder au portail loge ?",
     "reponse": "Votre loge reçoit un lien unique par email après validation de la demande d'accès. Ce lien est personnel et ne doit pas être partagé publiquement. En cas de perte, contactez l'administrateur via le formulaire de contact."},
    {"categorie": "membres", "section": "Portail loge", "ordre": 32,
     "question": "Comment s'abonner au calendrier de ma loge uniquement ?",
     "reponse": "Depuis le portail loge, la section calendrier propose deux liens : un calendrier global (toutes les loges) et un calendrier personnel (votre loge uniquement). Le lien personnel est sécurisé par un token unique."},

    # ── FAQ membres — section Contact & accès ────────────────────────────────
    {"categorie": "membres", "section": "Contact & accès", "ordre": 40,
     "question": "Comment contacter l'administrateur ?",
     "reponse": "Via le formulaire de contact disponible dans le menu (📬 Contact). L'administrateur reçoit le message immédiatement et répond par email."},
    {"categorie": "membres", "section": "Contact & accès", "ordre": 41,
     "question": "J'ai oublié le code d'accès annuel",
     "reponse": "Le code d'accès est renouvelé chaque saison. Contactez votre vénérable ou l'officier responsable de votre loge. Si vous n'avez pas leurs coordonnées, utilisez le formulaire de contact."},

    # ── FAQ traiteur ─────────────────────────────────────────────────────────
    {"categorie": "traiteur", "section": "Agapes & prestations", "ordre": 10,
     "question": "Comment voir les demandes d'agapes à venir ?",
     "reponse": "Depuis votre tableau de bord (🍽 Tableau de bord), toutes les demandes d'agapes validées et en attente sont listées avec le nombre de couverts et la date. Vous pouvez aussi consulter le Calendrier agapes (📅) pour une vue mensuelle."},
    {"categorie": "traiteur", "section": "Agapes & prestations", "ordre": 11,
     "question": "Comment confirmer une prestation au demandeur ?",
     "reponse": "Les loges utilisent le formulaire « Notifier le traiteur » pour vous informer de leurs besoins. Vous pouvez leur répondre directement par email depuis ce système ou les contacter via leurs coordonnées dans la demande."},
    {"categorie": "traiteur", "section": "Agapes & prestations", "ordre": 12,
     "question": "Comment exporter le planning des repas ?",
     "reponse": "Menu « 📋 Planning repas » → bouton Export Excel ou PDF. Vous pouvez filtrer par période (semaine, mois, saison) pour obtenir la liste des prestations avec nombre de couverts et coordonnées des loges."},

    {"categorie": "traiteur", "section": "Calendrier & réservations", "ordre": 20,
     "question": "Comment réserver une date pour le traiteur ?",
     "reponse": "Menu « ➕ Réserver » pour bloquer un créneau dans votre planning traiteur (mariage, événement externe, etc.) et éviter les conflits avec les demandes des loges."},
    {"categorie": "traiteur", "section": "Calendrier & réservations", "ordre": 21,
     "question": "Comment bloquer une date d'indisponibilité ?",
     "reponse": "Menu « 🔒 Bloquer » pour signaler vos jours de fermeture ou d'indisponibilité. Les loges seront ainsi informées que le service traiteur n'est pas disponible ces jours."},
    {"categorie": "traiteur", "section": "Calendrier & réservations", "ordre": 22,
     "question": "Comment voir le calendrier complet des tenues ?",
     "reponse": "Menu « 📅 Calendrier agapes » pour une vue mensuelle des agapes. Pour voir toutes les tenues (y compris sans agapes), accédez au calendrier général via l'accueil Kellermann."},

    {"categorie": "traiteur", "section": "Contact & accès", "ordre": 30,
     "question": "Comment contacter l'administrateur Kellermann ?",
     "reponse": "Utilisez le formulaire de contact (📬 Contact) dans le menu. L'administrateur reçoit et répond aux messages via la messagerie interne."},
    {"categorie": "traiteur", "section": "Contact & accès", "ordre": 31,
     "question": "J'ai oublié mon code d'accès traiteur",
     "reponse": "Le code d'accès traiteur est différent du code membres. Contactez l'administrateur Kellermann pour le récupérer ou le renouveler."},
]


def create_faq(apps, schema_editor):
    FAQ = apps.get_model('administration', 'FAQ')
    for item in FAQ_INITIAL:
        FAQ.objects.create(**item)


def delete_faq(apps, schema_editor):
    FAQ = apps.get_model('administration', 'FAQ')
    FAQ.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0012_faq'),
    ]

    operations = [
        migrations.RunPython(create_faq, delete_faq),
    ]
