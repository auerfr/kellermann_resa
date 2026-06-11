# ⚒ Kellermann Réservations

Outil de gestion des réservations du Temple Kellermann — loges, cabinets de réflexion, salles de réunion et banquets.

## Stack technique
- **Python 3.13** / **Django 5**
- **SQLite** (développement et production)
- **FullCalendar 6** pour la visualisation du calendrier
- **openpyxl** pour les imports/exports Excel
- **ReportLab** pour les exports PDF
- **Select2** sur les dropdowns

## Structure du projet
```
temple_project/
  apps/
    loges/          → Loges & Obédiences
    reservations/   → Réservations temples, salles, cabinets, banquets, récurrences
    calendrier/     → Vue calendrier (FullCalendar + API JSON)
    exports/        → CSV, Excel, PDF, Reporting
    administration/ → Tableau de bord, validation, import Excel, agapes traiteur
    auth_custom/    → Authentification visiteur (mot de passe annuel) et admin
  templates/        → HTML
  static/           → CSS, JS, images
```

## URL de production
**https://kellermanadmin.eu.pythonanywhere.com**

Hébergement : PythonAnywhere (plan gratuit)

## Workflow de déploiement

```bash
# 1. Développement local
python manage.py runserver

# 2. Pousser les modifications
git add .
git commit -m "Description des changements"
git push --force origin main

# 3. Sur PythonAnywhere (console Bash)
cd kellermann_resa
git fetch origin
git reset --hard origin/main
python manage.py migrate
# Puis : Reload via l'onglet Web
```

> **Note Proton Drive** : si le dossier `.git` a été supprimé par Proton Drive,
> relancer avant chaque push :
> ```bash
> git init
> git remote add origin https://github.com/auerfr/kellermann_resa.git
> git add . && git commit -m "restore" && git push --force origin main
> ```

## Installation locale (Windows)

```powershell
cd "C:\Users\francois-regis.auer\Proton Drive\auer.fr (1)\My files"
gh repo clone auerfr/kellermann_resa
cd kellermann_resa
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Puis ouvrir : http://127.0.0.1:8000

## Accès admin
- URL : http://127.0.0.1:8000/django-admin/
- Login : `admin` / Mot de passe : `Admin1234!` **(à changer immédiatement)**

## Voir aussi
- [CHANGELOG.md](CHANGELOG.md) — historique des fonctionnalités
