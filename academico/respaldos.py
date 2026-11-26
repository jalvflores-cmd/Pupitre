"""Respaldos de la base de datos SQLite (instalación local en el establecimiento).

Cada respaldo es un .zip con una copia consistente de la base (API de respaldo de SQLite),
guardado en RESPALDOS_DIR. Opcionalmente se copia a una carpeta adicional (disco externo
o carpeta sincronizada con Google Drive).
"""
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections

PREFIJO = "pupitre_"
NOMBRE_EN_ZIP = "pupitre.sqlite3"


class ErrorRespaldo(Exception):
    pass


@dataclass
class Respaldo:
    ruta: Path

    @property
    def nombre(self):
        return self.ruta.name

    @property
    def fecha(self):
        return datetime.fromtimestamp(self.ruta.stat().st_mtime)

    @property
    def tamano_mb(self):
        return self.ruta.stat().st_size / (1024 * 1024)


def usa_sqlite():
    return settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def ruta_base():
    return Path(settings.DATABASES["default"]["NAME"])


def carpeta():
    settings.RESPALDOS_DIR.mkdir(parents=True, exist_ok=True)
    return settings.RESPALDOS_DIR


def listar():
    if not settings.RESPALDOS_DIR.exists():
        return []
    archivos = [Respaldo(p) for p in settings.RESPALDOS_DIR.glob(f"{PREFIJO}*.zip")]
    return sorted(archivos, key=lambda r: r.ruta.stat().st_mtime, reverse=True)


def ultimo():
    lista = listar()
    return lista[0] if lista else None


def _copiar_base(destino: Path):
    origen = sqlite3.connect(str(ruta_base()))
    copia = sqlite3.connect(str(destino))
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()


def _configuracion():
    from .models import Establecimiento

    est = Establecimiento.objects.order_by("pk").first()
    extra = (est.respaldo_carpeta_extra or "").strip() if est else ""
    conservar = est.respaldo_conservar if est and est.respaldo_conservar else 30
    return extra, conservar


def crear(motivo="manual"):
    """Crea un respaldo y devuelve (Respaldo, lista de advertencias)."""
    if not usa_sqlite():
        raise ErrorRespaldo("Los respaldos automáticos solo están disponibles en la instalación local (SQLite).")
    advertencias = []
    marca = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino = carpeta() / f"{PREFIJO}{marca}_{motivo}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / NOMBRE_EN_ZIP
        _copiar_base(copia)
        with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(copia, NOMBRE_EN_ZIP)
            z.writestr("LEAME.txt", f"Respaldo de Pupitre creado el {datetime.now():%d-%m-%Y %H:%M} ({motivo}).\n"
                                    "Para restaurarlo use restaurar.bat en el computador servidor.\n")
    extra, conservar = _configuracion()
    _rotar(conservar)
    if extra:
        try:
            carpeta_extra = Path(extra)
            carpeta_extra.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destino, carpeta_extra / destino.name)
            _rotar(conservar, carpeta_extra)
        except OSError as e:
            advertencias.append(f"No se pudo copiar a la carpeta adicional «{extra}»: {e}")
    return Respaldo(destino), advertencias


def _rotar(conservar, en=None):
    archivos = sorted((en or settings.RESPALDOS_DIR).glob(f"{PREFIJO}*.zip"), key=lambda p: p.stat().st_mtime,
                      reverse=True)
    for viejo in archivos[conservar:]:
        try:
            viejo.unlink()
        except OSError:
            pass


def necesita_respaldo_diario(horas=24):
    r = ultimo()
    return r is None or (datetime.now() - r.fecha).total_seconds() > horas * 3600


def verificar_zip(archivo: Path):
    try:
        with zipfile.ZipFile(archivo) as z:
            if NOMBRE_EN_ZIP not in z.namelist():
                raise ErrorRespaldo("El archivo no es un respaldo de Pupitre.")
    except zipfile.BadZipFile:
        raise ErrorRespaldo("El archivo está dañado o no es un .zip de respaldo.")


def restaurar(archivo: Path):
    """Reemplaza la base actual por la del respaldo. Antes guarda un respaldo de seguridad.
    Debe ejecutarse con el servidor detenido (restaurar.bat lo hace)."""
    archivo = Path(archivo)
    verificar_zip(archivo)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archivo) as z:
            z.extract(NOMBRE_EN_ZIP, tmp)
        nueva = Path(tmp) / NOMBRE_EN_ZIP
        con = sqlite3.connect(str(nueva))
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        if not ok or "academico_estudiante" not in tablas:
            raise ErrorRespaldo("El respaldo no pasó la verificación de integridad. No se cambió nada.")
        seguridad = None
        if ruta_base().exists():
            seguridad, _ = crear("antes_de_restaurar")
        connections.close_all()
        destino = ruta_base()
        for sufijo in ("-wal", "-shm"):
            extra = Path(str(destino) + sufijo)
            if extra.exists():
                extra.unlink()
        shutil.copy2(nueva, destino)
    return seguridad
