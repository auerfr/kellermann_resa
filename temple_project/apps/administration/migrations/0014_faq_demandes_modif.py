from django.db import migrations

NEW_ENTRIES = [
    # ── Réservations : capacité des salles ──────────────────────────────────
    {"categorie": "membres", "section": "Réservations", "ordre": 17,
     "question": "Comment connaître la capacité des salles de réunion ?",
     "reponse": "La capacité de chaque salle est indiquée directement dans le formulaire de réservation, entre parenthèses à côté du nom de la salle (ex : Salle Liberté (20 pers.)). Choisissez la salle adaptée à votre groupe."},

    # ── Portail loge : demande de modification / annulation ─────────────────
    {"categorie": "membres", "section": "Portail loge", "ordre": 33,
     "question": "Comment demander l'annulation ou le déplacement d'une tenue depuis le portail ?",
     "reponse": (
         "Depuis votre portail loge, les réservations futures validées affichent un bouton "
         "« Modifier / Annuler ». Cliquez dessus pour soumettre une demande d'annulation ou de "
         "déplacement de date.\n\n"
         "Important : seules les réservations dont la date est dans le futur peuvent faire l'objet "
         "d'une demande. Pour un déplacement, indiquez la nouvelle date souhaitée (disponibilité "
         "vérifiée automatiquement) ainsi qu'un motif. La demande est ensuite validée par "
         "l'administrateur, qui vous confirmera l'action par email."
     )},
]


def add_faq(apps, schema_editor):
    FAQ = apps.get_model('administration', 'FAQ')
    # Update the existing "modifier ou annuler" entry to mention the portail
    FAQ.objects.filter(
        categorie='membres',
        section='Réservations',
        ordre=14,
    ).update(
        reponse=(
            "Depuis votre portail loge, les réservations futures validées proposent un bouton "
            "« Modifier / Annuler » : vous pouvez soumettre une demande d'annulation ou de "
            "déplacement de date directement en ligne. "
            "Pour les demandes sans accès au portail, utilisez le formulaire de contact "
            "(menu « Contact ») en précisant la date, le temple et la loge concernés. "
            "L'administrateur valide toutes les demandes avant de les appliquer."
        )
    )
    # Add the new entries (skip if already present to stay idempotent)
    for item in NEW_ENTRIES:
        FAQ.objects.get_or_create(
            categorie=item["categorie"],
            section=item["section"],
            ordre=item["ordre"],
            defaults={
                "question": item["question"],
                "reponse":  item["reponse"],
                "actif":    True,
            },
        )


def reverse_faq(apps, schema_editor):
    FAQ = apps.get_model('administration', 'FAQ')
    # Restore original "modifier ou annuler" text
    FAQ.objects.filter(
        categorie='membres', section='Réservations', ordre=14,
    ).update(
        reponse=(
            "Les modifications et annulations passent par l'administrateur. "
            "Utilisez le formulaire de contact (menu « Contact ») en précisant la date, "
            "le temple et la loge concernés. L'admin peut également effectuer les modifications "
            "directement."
        )
    )
    for item in NEW_ENTRIES:
        FAQ.objects.filter(
            categorie=item["categorie"],
            section=item["section"],
            ordre=item["ordre"],
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0013_faq_initial_data'),
    ]

    operations = [
        migrations.RunPython(add_faq, reverse_faq),
    ]
