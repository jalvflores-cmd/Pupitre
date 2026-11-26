from django.conf import settings

from .models import Establecimiento, Perfil, SolicitudCambio
from .permisos import puede_ver_funcionarios, es_gestion, es_solo_lectura, gestiona_convivencia, puede_editar_contacto, rol_de, ve_todo


USUARIOS_DEMO = [
    ("sostenedor", "Sostenedor(a)"), ("director", "Director(a)"), ("utp", "Jefe(a) de UTP"),
    ("inspector", "Inspector(a) general"), ("convivencia", "Encargado(a) de convivencia"),
    ("profe.historia", "Profesor(a) de asignatura"), ("profe.lenguaje", "Profesor(a) jefe"),
]


def _marca(est):
    """Logo y color institucional configurados por el establecimiento."""
    from zlib import crc32

    color = est.color_principal or ""
    rgb = ", ".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5)) if len(color) == 7 else ""
    return {"logo_url": f"/logo.png?v={crc32(bytes(est.logo))}" if est.logo else "",
            "color_institucional": color, "color_institucional_rgb": rgb}


def rol(request):
    est = Establecimiento.actual()
    if not request.user.is_authenticated:
        return {"modo_demo": settings.MODO_DEMO, "usuarios_demo": USUARIOS_DEMO if settings.MODO_DEMO else [],
                "establecimiento": est, **_marca(est)}
    gestion = es_gestion(request.user)
    if gestion:
        pendientes = SolicitudCambio.objects.filter(estado=SolicitudCambio.Estado.PENDIENTE).count()
    else:
        pendientes = None
    return {
        "modo_demo": settings.MODO_DEMO,
        "es_gestion": gestion,
        "solicitudes_pendientes": pendientes,
        "es_profesor_jefe": not gestion and request.user.jefaturas.exists(),
        "ve_todo": ve_todo(request.user),
        "ve_funcionarios": puede_ver_funcionarios(request.user),
        "gestiona_convivencia": gestiona_convivencia(request.user),
        "puede_editar_contacto": puede_editar_contacto(request.user),
        "solo_lectura": es_solo_lectura(request.user),
        "rol_usuario": Perfil.Rol(rol_de(request.user)).label,
        "establecimiento": est, **_marca(est),
        "respaldos_disponibles": gestion and settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"),
    }
