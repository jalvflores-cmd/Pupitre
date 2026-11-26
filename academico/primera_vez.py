"""Si la plataforma no tiene usuarios (instalación nueva), todo lleva al asistente de primera configuración."""
from django.contrib.auth.models import User
from django.shortcuts import redirect

_configurada = False


def plataforma_configurada():
    global _configurada
    if not _configurada:
        _configurada = User.objects.exists()
    return _configurada


class PrimeraConfiguracionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ruta = request.path
        if not ruta.startswith(("/static/", "/bienvenida/")) and not plataforma_configurada():
            return redirect("bienvenida")
        return self.get_response(request)
