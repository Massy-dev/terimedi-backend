#!/bin/sh
set -e

echo "🔥 PROD SETTINGS LOADED 🔥"

python manage.py migrate



# Vérifier et créer les dossiers de migrations seulement si nécessaire
for app in users pharmacies orders notifications; do
  MIGRATION_DIR="./apps/$app/migrations"
  if [ ! -d "$MIGRATION_DIR" ]; then
    mkdir -p "$MIGRATION_DIR"
    echo "✅ Created migration folder for $app"
  fi

  # Créer __init__.py si absent
  if [ ! -f "$MIGRATION_DIR/__init__.py" ]; then
    touch "$MIGRATION_DIR/__init__.py"
    echo "✅ Created __init__.py for $app migrations"
  fi
done

# Créer les migrations uniquement si elles n'existent pas
echo "🛠 Checking for pending migrations..."
python manage.py makemigrations --check --dry-run || python manage.py makemigrations users pharmacies orders notifications

# Appliquer toutes les migrations
echo "📦 Running migrations..."

python manage.py migrate --noinput

# Créer le superuser automatiquement si il n'existe pas
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(phone='0700000000').exists():
    User.objects.create_superuser(
    phone='0700000000', password='1833terimedi')
    print('Superuser created successfully.')
else:
    print('Superuser already exists.')
"
# Collecter les fichiers statiques
echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

# Lancer Daphne
echo "🚀 Starting Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application
