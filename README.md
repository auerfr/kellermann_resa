# ⚒ Kellermann Réservations

Application web de gestion des réservations de temples et cabinets de réflexion.

## Stack technique
- **Python 3.11+** / **Django 5.0**
- **SQLite** (développement) → **PostgreSQL** (production)
- **FullCalendar 6** pour la visualisation
- **openpyxl** pour les imports/exports Excel

## Installation rapide (Windows)

```powershell
# 1. Cloner le dépôt
cd "C:\Users\francois-regis.auer\Proton Drive\auer.fr (1)\My files"
gh repo clone auerfr/kellermann_resa
cd kellermann_resa

# 2. Lancer l'installation automatique
.\SETUP_WINDOWS.ps1

# 3. Démarrer le serveur
python manage.py runserver
```

Puis ouvrir : http://127.0.0.1:8000

## Accès admin
- URL : http://127.0.0.1:8000/django-admin/
- Login : `admin` / Mot de passe : `Admin1234!` **(à changer immédiatement)**

## Structure du projet
```
temple_project/
  apps/
    loges/          → Loges & Obédiences
    reservations/   → Modèle de données principal
    calendrier/     → Vue calendrier (FullCalendar + API JSON)
    exports/        → CSV, Excel, Reporting
    administration/ → Tableau de bord, validation, import Excel
  templates/        → HTML
  static/           → CSS, JS, images
  fixtures/         → Données initiales
```
