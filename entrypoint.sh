#!/bin/sh
set -e

echo "🔥 PROD SETTINGS LOADED en entrypoint.sh 🔥"

echo "PORT = $PORT"

# Fallback Railway
if [ -z "$PORT" ]; then
  export PORT=8000
fi

echo "📦 Running migrations..."
python manage.py migrate --noinput

echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Daphne on port $PORT..."

exec daphne -b 0.0.0.0 -p $PORT config.asgi:application