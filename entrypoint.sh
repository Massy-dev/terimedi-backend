#!/bin/sh
set -e

echo "🔥 PROD SETTINGS LOADED 🔥"

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "📦 Running migrations..."
    python manage.py migrate --noinput
fi

# ✅ Création du superuser automatique
if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "👤 Creating superuser..."

    python manage.py shell << END
from django.contrib.auth import get_user_model
import os

User = get_user_model()

phone = os.getenv("DJANGO_SUPERUSER_PHONE", "0708000000")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "1833production")

if not User.objects.filter(phone=phone).exists():
    User.objects.create_superuser(phone=phone, password=password)
    print("✅ Superuser created")
elif User.objects.filter(phone=phone).exists():
    print("ℹ️ Superuser already exists")
else:
    print("❌ Superuser creation failed")
END
fi

echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Daphne..."
echo "PORT is $PORT"

exec daphne -b 0.0.0.0 -p ${PORT} config.asgi:application --verbosity 2