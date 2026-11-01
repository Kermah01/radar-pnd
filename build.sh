#!/usr/bin/env bash
# Script de build Render : dépendances, fichiers statiques, migrations, données PND.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py load_pnd
python manage.py load_gcpnd

# Comptes administrateur et démonstration (idempotent).
# CREATE_DEMO=1 crée aussi les codes de démonstration DEMO-DECO-000x / DEMO-PRO0-000x.
if [ "${CREATE_DEMO:-0}" = "1" ]; then
  python manage.py init_demo
elif [ -n "${ADMIN_PASSWORD:-}" ]; then
  python manage.py init_demo --sans-codes-demo
fi
