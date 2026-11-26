"""Configuración de la plataforma Pupitre (gestión curricular).

Todas las opciones sensibles se leen desde variables de entorno (ver README.md).
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).lower() in ("1", "true", "si", "sí", "yes")


# Instalación local (un computador del establecimiento, accesible solo desde su red interna).
# La activan los scripts de la carpeta windows/ con PUPITRE_LOCAL=true.
MODO_LOCAL = env_bool("PUPITRE_LOCAL", False)
DATOS_DIR = Path(os.environ.get("PUPITRE_DATOS", BASE_DIR / "datos"))
RESPALDOS_DIR = Path(os.environ.get("PUPITRE_RESPALDOS", BASE_DIR / "respaldos"))


def _clave_local():
    """En modo local la clave secreta se genera una vez y se guarda junto a los datos."""
    from django.core.management.utils import get_random_secret_key

    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    archivo = DATOS_DIR / "clave_secreta.txt"
    if not archivo.exists():
        archivo.write_text(get_random_secret_key(), encoding="utf-8")
    return archivo.read_text(encoding="utf-8").strip()


if MODO_LOCAL:
    SECRET_KEY = os.environ.get("SECRET_KEY") or _clave_local()
    DEBUG = env_bool("DEBUG", False)
    ALLOWED_HOSTS = ["*"]  # se accede por el nombre o la IP del equipo dentro de la red de la escuela
    os.environ.setdefault("COOKIES_SEGURAS", "false")  # red interna sin HTTPS
else:
    SECRET_KEY = os.environ.get("SECRET_KEY", "solo-para-desarrollo-cambiar-en-produccion")
    DEBUG = env_bool("DEBUG", True)
    ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Render (y servicios similares) informan el dominio público en esta variable.
_HOST_EXTERNO = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _HOST_EXTERNO:
    ALLOWED_HOSTS.append(_HOST_EXTERNO)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_HOST_EXTERNO}")

# Modo demostración: muestra los usuarios de prueba en la pantalla de ingreso.
MODO_DEMO = env_bool("MODO_DEMO", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "academico",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "academico.primera_vez.PrimeraConfiguracionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "academico.context_processors.rol",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de datos: SQLite por defecto; en producción usar DATABASE_URL (PostgreSQL).
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{(DATOS_DIR / 'pupitre.sqlite3') if MODO_LOCAL else (BASE_DIR / 'db.sqlite3')}",
        conn_max_age=600,
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # Varios profesores a la vez: espera en vez de fallar si la base está ocupada.
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"].setdefault("OPTIONS", {}).update({
        "timeout": 20, "transaction_mode": "IMMEDIATE",
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
    })

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# Tamaño máximo de archivos Excel subidos (10 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

if not DEBUG:
    if SECRET_KEY.startswith("solo-para-desarrollo"):
        raise RuntimeError("Defina la variable de entorno SECRET_KEY antes de ejecutar en producción.")
    SESSION_COOKIE_SECURE = env_bool("COOKIES_SEGURAS", True)
    CSRF_COOKIE_SECURE = env_bool("COOKIES_SEGURAS", True)
    if not MODO_LOCAL:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
