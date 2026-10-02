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
         "Pour un déplacement : sélectionnez la nouvelle date souhaitée. La disponibilité du "
         "créneau (même temple/salle, même horaire) est vérifiée en temps réel et le résultat "
         "s'affiche immédiatement sous le champ de date (✓ Créneau disponible, "
         "⚠ Demande en cours, ou ✗ Créneau occupé).\n\n"
         "Seules les réservations futures peuvent faire l'objet d'une demande. La réservation "
         "reste active jusqu'à validation par l'administrateur, qui vous confirmera l'action par email."
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
    # Add the new entries (upsert to stay idempotent)
    for item in NEW_ENTRIES:
        obj, created = FAQ.objects.get_or_create(
            categorie=item["categorie"],
            section=item["section"],
            ordre=item["ordre"],
            defaults={
                "question": item["question"],
                "reponse":  item["reponse"],
                "actif":    True,
            },
        )
        if not created:
            obj.question = item["question"]
            obj.reponse  = item["reponse"]
            obj.save(update_fields=["question", "reponse"])


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
