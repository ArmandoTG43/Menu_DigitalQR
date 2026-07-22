#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# 🔥 EJECUTAR RESETEO DE BASE DE DATOS (SOLO UNA VEZ)
python reset_db.py