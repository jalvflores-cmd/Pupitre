"""Fija el establecimiento con que trabaja cada petición y controla los módulos activos."""
from django.shortcuts import redirect, render

from . import tenencia

# Rutas permitidas al superadministrador sin haber elegido un establecimiento
LIBRES_SUPERADMIN = ("/plataforma/", "/red/", "/personal/", "/asistente/", "/static/", "/salir/", "/ingresar/", "/clave/", "/admin/", "/logo.png")
# Rutas de cada módulo (si el establecimiento no tiene el módulo, no se puede entrar)
RUTAS_MODULO = {
    "convivencia": ("/convivencia/", "/anotaciones/", "/entrevistas/", "/redes/"),
    "funcionarios": ("/funcionarios/",),
    "asistencia_personal": ("/asistencia-personal/",),
    "sep": ("/pme/",),
}


def es_superadmin(user):
    perfil = getattr(user, "perfil", None) if user.is_authenticated else None
    return bool(perfil and perfil.rol == "SUPERADMIN")


def perfil_de_sostenedor(user):
    perfil = getattr(user, "perfil", None) if user.is_authenticated else None
    return perfil if perfil and perfil.de_sostenedor else None


def establecimiento_de(request):
    from .models import Establecimiento

    user = request.user
    if not user.is_authenticated:
        return None
    if es_superadmin(user):
        pk = request.session.get("establecimiento_id")
        return Establecimiento.objects.filter(pk=pk).first() if pk else None
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.de_sostenedor:  # elige entre los establecimientos de su sostenedor
        propios = Establecimiento.objects.filter(sostenedor_id=perfil.sostenedor_id)
        pk = request.session.get("establecimiento_id")
        est = propios.filter(pk=pk).first() if pk else None
        if est is None and propios.count() == 1:
            est = propios.first()
        return est
    if perfil and perfil.establecimiento_id:
        return perfil.establecimiento
    return Establecimiento.objects.order_by("pk").first()


class EstablecimientoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        est = establecimiento_de(request)
        request.establecimiento = est
        ruta = request.path
        if request.user.is_authenticated:
            if es_superadmin(request.user) and est is None and not ruta.startswith(LIBRES_SUPERADMIN):
                return redirect("plataforma")
            perfil_sost = perfil_de_sostenedor(request.user)
            if perfil_sost and not perfil_sost.sostenedor.activo and not ruta.startswith(("/salir/", "/static/")):
                return render(request, "academico/aviso.html", {
                    "titulo": "Sostenedor desactivado",
                    "texto": "El acceso de este sostenedor está suspendido. Contacte al administrador de la plataforma."},
                    status=403)
            if est is None and perfil_sost and not ruta.startswith(LIBRES_SUPERADMIN):
                return redirect("red")
            if est is not None and not est.activo and not es_superadmin(request.user) \
                    and not ruta.startswith(("/salir/", "/static/")):
                return render(request, "academico/aviso.html", {
                    "titulo": "Establecimiento desactivado",
                    "texto": "El acceso de este establecimiento está suspendido. Contacte al administrador de la plataforma."},
                    status=403)
            if est is not None:
                for modulo, prefijos in RUTAS_MODULO.items():
                    if ruta.startswith(prefijos) and not est.tiene_modulo(modulo):
                        return render(request, "academico/aviso.html", {
                            "titulo": "Módulo no habilitado",
                            "texto": "Este módulo no está activo para su establecimiento."}, status=403)
        token = tenencia.fijar(est)
        try:
            return self.get_response(request)
        finally:
            tenencia.restaurar(token)
