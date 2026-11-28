#!/bin/sh
# Arranque del servidor: aplica migraciones, lanza gunicorn y, si MODO_DEMO=true, carga los datos de demostración
# en segundo plano (así el servidor responde de inmediato y el despliegue no queda esperando la carga).
set -e
python manage.py migrate --noinput
if [ "$MODO_DEMO" = "true" ]; then
  (timeout 900 python manage.py datos_demo || echo "datos_demo no terminó correctamente") &
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 120
