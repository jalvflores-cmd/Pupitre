#!/bin/sh
# Arranque del servidor: aplica migraciones, carga datos de demostración (si MODO_DEMO=true) y lanza gunicorn.
set -e
python manage.py migrate --noinput
if [ "$MODO_DEMO" = "true" ]; then
  python manage.py datos_demo
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 120
