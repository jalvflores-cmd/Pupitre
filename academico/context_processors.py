from .models import Establecimiento, Perfil
from .permisos import es_gestion, rol_de


def rol(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "es_gestion": es_gestion(request.user),
        "rol_usuario": Perfil.Rol(rol_de(request.user)).label,
        "establecimiento": Establecimiento.actual(),
    }
