# Kellermann Resa - Installation
Write-Host "=== Installation Kellermann Resa ===" -ForegroundColor Cyan
Write-Host "`n[1/7] Verification Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "  OK : $pythonVersion" -ForegroundColor Green
Write-Host "`n[2/7] Creation environnement virtuel..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) { python -m venv venv }
Write-Host "  OK" -ForegroundColor Green
Write-Host "`n[3/7] Activation..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "  OK" -ForegroundColor Green
Write-Host "`n[4/7] Installation dependances..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
Write-Host "  OK" -ForegroundColor Green
Write-Host "`n[5/7] Fichier .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Host "  OK" -ForegroundColor Green
Write-Host "`n[6/7] Base de donnees..." -ForegroundColor Yellow
python manage.py migrate
Write-Host "  OK" -ForegroundColor Green
Write-Host "`n[7/7] Compte admin..." -ForegroundColor Yellow
python manage.py createsuperuser --noinput --username admin --email admin@kellermann.fr 2>$null
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='admin'); u.set_password('Admin1234!'); u.save()"
Write-Host "  OK : login=admin / mdp=Admin1234!" -ForegroundColor Green
python manage.py loaddata temple_project/fixtures/initial_data.json 2>$null
Write-Host "`n=== Installation terminee ! ===" -ForegroundColor Cyan
Write-Host "Lancer le serveur : python manage.py runserver" -ForegroundColor Yellow
