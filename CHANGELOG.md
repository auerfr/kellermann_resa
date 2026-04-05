# Kellermann Réservations — Changelog

## Version actuelle — Avril 2026

### Nouvelles fonctionnalités
- Calendrier : affichage jours fériés et vacances scolaires Zone B
- Calendrier : filtres cabinet/banquet, légende enrichie
- Réservation cabinets de réflexion avec disponibilité en temps réel et préférence
- Réservation banquet d'ordre (L'Oie et le Grill)
- Demande de règle de récurrence par les loges
- Vue synthétique agapes & traiteur avec export Excel et PDF
- Export PDF planning mensuel par temple
- SMTP dynamique configuré depuis l'interface admin (Gmail)
- Rites maçonniques étendus sur les loges (RAPMM, RMFR, RF/REAA, Émulation, Marque)
- Reporting enrichi : KPIs, graphiques Chart.js, tableau obédiences
- Gestion saison : suppression/regénération/reset complet
- Backup/restauration base de données
- Select2 sur tous les dropdowns

### Corrections
- Import circulaire reservations/administration résolu
- ALLOWED_HOSTS configuré définitivement dans settings.py
- Filtres rites dans liste loges
- Noms réels des cabinets affichés dans les formulaires

### Infrastructure
- .protondriveignore pour limiter les conflits Proton Drive
- Script backup_db.py pour sauvegarde automatique
- email_utils.py pour SMTP dynamique
