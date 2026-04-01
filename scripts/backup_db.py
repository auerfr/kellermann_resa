import os
import shutil
from datetime import datetime
from pathlib import Path

# Chemins
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db.sqlite3"
BACKUP_DIR = BASE_DIR / "backups"

# Créer le dossier backups si nécessaire
BACKUP_DIR.mkdir(exist_ok=True)

# Nom du fichier de sauvegarde avec date
date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = BACKUP_DIR / f"backup_kellermann_{date_str}.sqlite3"

# Copier la base
shutil.copy2(DB_PATH, backup_path)
print(f"Sauvegarde créée : {backup_path}")

# Garder uniquement les 10 dernières sauvegardes
backups = sorted(BACKUP_DIR.glob("backup_kellermann_*.sqlite3"))
if len(backups) > 10:
    for old in backups[:-10]:
        old.unlink()
        print(f"Ancienne sauvegarde supprimée : {old}")

print("Terminé.")