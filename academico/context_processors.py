from django.conf import settings

from .models import Establecimiento, Perfil, SolicitudCambio
from .permisos import puede_ver_funcionarios, es_gestion, es_solo_lectura, gestiona_convivencia, puede_editar_contacto, rol_de, ve_todo


USUARIOS_DEMO = [
    ("sostenedor", "Sostenedor(a)"), ("director", "Director(a)"), ("utp", "Jefe(a) de UTP"),
    ("inspector", "Inspector(a) general"), ("convivencia", "Encargado(a) de convivencia"),
    ("profe.historia", "Profesor(a) de asignatura"), ("profe.lenguaje", "Profesor(a) jefe"),
]


def rol(request):
    if not request.user.is_authenticated:
        return {"modo_demo": settings.MODO_DEMO, "usuarios_demo": USUARIOS_DEMO if settings.MODO_DEMO else [],
                "establecimiento": Establecimiento.actual()}
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
        "establecimiento": Establecimiento.actual(),
    }
