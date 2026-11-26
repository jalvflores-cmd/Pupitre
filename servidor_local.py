"""Servidor de Pupitre para la instalación local en un computador del establecimiento.

- Aplica las actualizaciones pendientes de la base de datos.
- Atiende a los computadores de la red interna en el puerto 8000 (o PUPITRE_PUERTO).
- Hace un respaldo al iniciar y luego uno cada día, de forma automática.

Se ejecuta con windows/iniciar_pupitre.bat (lo programa el instalador para que arranque con el equipo).
"""
import logging
import os
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("PUPITRE_LOCAL", "true")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402

settings.DATOS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(settings.DATOS_DIR / "servidor.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger("pupitre")


def respaldos_automaticos():
    from academico import respaldos

    while True:
        try:
            if respaldos.necesita_respaldo_diario(horas=23):
                r, advertencias = respaldos.crear("automatico")
                log.info("Respaldo automático creado: %s", r.nombre)
                for a in advertencias:
                    log.warning(a)
        except Exception:  # nunca detener el servidor por un respaldo fallido
            log.exception("Falló el respaldo automático")
        time.sleep(30 * 60)


def main():
    puerto = int(os.environ.get("PUPITRE_PUERTO", "8000"))
    call_command("migrate", interactive=False, verbosity=0)
    threading.Thread(target=respaldos_automaticos, daemon=True).start()
    from waitress import serve

    from config.wsgi import application

    log.info("Pupitre disponible en http://localhost:%s (y desde la red interna con el nombre o IP de este equipo)",
             puerto)
    serve(application, host="0.0.0.0", port=puerto, threads=8)


if __name__ == "__main__":
    main()
