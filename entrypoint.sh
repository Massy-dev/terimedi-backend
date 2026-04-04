#!/bin/sh
set -e

echo "🔥 PROD SETTINGS LOADED 🔥"

# Vérifier si migrations sont demandées (optionnel)
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "📦 Running migrations..."
    python manage.py migrate --noinput
fi

echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Daphne..."
echo "PORT is $PORT"
echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT} config.asgi:application --verbosity 2