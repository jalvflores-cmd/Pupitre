from .models import Establecimiento, Perfil, SolicitudCambio
from .permisos import es_gestion, rol_de


def rol(request):
    if not request.user.is_authenticated:
        return {}
    gestion = es_gestion(request.user)
    if gestion:
        pendientes = SolicitudCambio.objects.filter(estado=SolicitudCambio.Estado.PENDIENTE).count()
    else:
        pendientes = None
    return {
        "es_gestion": gestion,
        "solicitudes_pendientes": pendientes,
        "es_profesor_jefe": not gestion and request.user.jefaturas.exists(),
        "rol_usuario": Perfil.Rol(rol_de(request.user)).label,
        "establecimiento": Establecimiento.actual(),
    }
