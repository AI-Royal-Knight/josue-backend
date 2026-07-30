#!/bin/sh
set -e

# Ensure the SQLite data directory exists
mkdir -p /app/sqlite_data

# Select the correct settings module (wsgi.py defaults to the empty config.settings package)
if [ "${ENVIRONMENT:-dev}" = "prod" ]; then
  export DJANGO_SETTINGS_MODULE="config.settings.prod"
else
  export DJANGO_SETTINGS_MODULE="config.settings.dev"
fi

echo "==> Using settings: $DJANGO_SETTINGS_MODULE"
echo "==> Running database migrations..."
uv run python manage.py migrate --noinput

echo "==> Collecting static files..."
uv run python manage.py collectstatic --noinput

echo "==> Starting Gunicorn..."
exec uv run gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
