from django.conf import settings

from .models import Establecimiento, Perfil, SolicitudCambio
from .permisos import puede_ver_funcionarios, es_gestion, es_solo_lectura, gestiona_convivencia, puede_editar_contacto, rol_de, ve_todo


USUARIOS_DEMO = [
    ("Plataforma", [("superadmin", "Superadministrador(a)")]),
    ("Corporación Educacional Ñuble · sostenedor de la escuela y los 3 liceos", [
        ("admin.red", "Administrador(a) del sostenedor"), ("sostenedor.red", "Sostenedor(a)")]),
    ("Escuela Gabriela Mistral · Básica", [
        ("admin.escuela", "Administrador(a) de plataforma"), ("sostenedor", "Sostenedor(a)"), ("director", "Director(a)"), ("utp", "Jefe(a) de UTP"),
        ("inspector", "Inspector(a) general"), ("convivencia", "Encargado(a) de convivencia"),
        ("profe.historia", "Profesor(a) de asignatura"), ("profe.lenguaje", "Profesor(a) jefe")]),
    ("Liceo Científico-Humanista", [("director.hc", "Director(a)"), ("utp.hc", "Jefe(a) de UTP"),
                                    ("profe.hc", "Profesor(a) jefe")]),
    ("Liceo Técnico-Profesional", [("director.tp", "Director(a)"), ("utp.tp", "Jefe(a) de UTP"),
                                   ("profe.tp", "Profesor(a) de especialidad")]),
    ("Liceo Polivalente", [("director.poli", "Director(a)"), ("utp.poli", "Jefe(a) de UTP"),
                           ("profe.poli", "Profesor(a) jefe")]),
]


def _marca(est):
    """Logo y color institucional configurados por el establecimiento."""
    from zlib import crc32

    color = est.color_principal or ""
    rgb = ", ".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5)) if len(color) == 7 else ""
    return {"logo_url": f"/logo.png?v={crc32(bytes(est.logo))}" if est.logo else "",
            "color_institucional": color, "color_institucional_rgb": rgb}


def rol(request):
    from .permisos import es_superadmin

    est = getattr(request, "establecimiento", None) or Establecimiento.actual()
    if not request.user.is_authenticated:
        if Establecimiento.objects.count() > 1:  # plataforma con varios colegios: ingreso genérico
            est = Establecimiento(nombre="")
        return {"modo_demo": settings.MODO_DEMO, "usuarios_demo": USUARIOS_DEMO if settings.MODO_DEMO else [],
                "establecimiento": est, **_marca(est)}
    superadmin = es_superadmin(request.user)
    perfil = getattr(request.user, "perfil", None)
    de_sostenedor = bool(perfil and perfil.de_sostenedor)
    if superadmin and getattr(request, "establecimiento", None) is None:
        est = Establecimiento(nombre="Plataforma Pupitre")
    elif de_sostenedor and getattr(request, "establecimiento", None) is None:
        est = Establecimiento(nombre=perfil.sostenedor.nombre)
    extra = {"es_superadmin": superadmin, "de_sostenedor": de_sostenedor,
             "nombre_sostenedor": perfil.sostenedor.nombre if de_sostenedor else "",
             "mod_convivencia": est.tiene_modulo("convivencia") if est.pk else True,
             "mod_funcionarios": est.tiene_modulo("funcionarios") if est.pk else True,
             "mod_asistencia_personal": est.tiene_modulo("asistencia_personal") if est.pk else True,
             "mod_sep": est.tiene_modulo("sep") if est.pk else True,
             "ve_administrativo": _ve_administrativo(request.user)}
    gestion = es_gestion(request.user)
    if gestion:
        pendientes = SolicitudCambio.objects.filter(estado=SolicitudCambio.Estado.PENDIENTE).count()
    else:
        pendientes = None
    return {
        **extra,
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
        "ve_alertas": _ve_alertas(request.user),
        "respaldos_disponibles": gestion and settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"),
        **_asistente(request),
    }


def _asistente(request):
    """Avisos del asistente para la campana y el aviso emergente (una vez al día por sesión)."""
    from django.utils import timezone

    from .asistente import avisos_de

    if not hasattr(request, "session"):
        return {}
    avisos = avisos_de(request)
    hoy = timezone.localdate().isoformat()
    popup = bool(avisos) and request.method == "GET" and request.path != "/asistente/" \
        and request.session.get("asistente_popup") != hoy
    if popup:
        request.session["asistente_popup"] = hoy
    return {"avisos_asistente": avisos, "n_avisos": len(avisos), "mostrar_popup": popup}


def _ve_alertas(user):
    from .alertas import ve_alertas

    return ve_alertas(user)


def _ve_administrativo(user):
    from .asistencia_personal import puede_ver

    return puede_ver(user)
