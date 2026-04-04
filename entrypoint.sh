#!/bin/sh
set -e

echo "🔥 PROD SETTINGS LOADED 🔥"

# Vérifier si migrations sont demandées (optionnel)
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "📦 Running migrations..."
    python manage.py migrate --noinput
fi

python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser(
        email='$DJANGO_SUPERUSER_EMAIL',
        password='$DJANGO_SUPERUSER_PASSWORD'
    )
    print('Superuser créé')
else:
    print('Superuser existe déjà')
"


echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Daphne..."
echo "PORT is $PORT"
echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT} config.asgi:application --verbosity 2