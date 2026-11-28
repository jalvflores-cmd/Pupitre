"""Asistente de seguimiento: revisa, según el rol de cada usuario, lo que está pendiente o por vencer y lo muestra
como avisos (campana de la barra superior, aviso emergente al ingresar y la página «Asistente»).

Las reglas son fijas y transparentes (no usan IA). Opcionalmente, si el establecimiento lo activa y la plataforma
tiene configurada la clave ANTHROPIC_API_KEY, el asistente pide a Claude sugerencias redactadas a partir de los
avisos del día. A la IA solo se envían el rol, la fecha y los títulos y conteos de los avisos: nunca nombres ni RUT
de estudiantes.
"""
import datetime
import logging
import os
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (AccionPME, Anotacion, AsignaturaCurso, Clase, Curso, Establecimiento, EstadoDerivacion,
                     Funcionario, AsistenciaFuncionario, HorarioClase, Perfil, Evaluacion, SolicitudCambio, anio_actual)
from .permisos import _perfil, es_gestion, exigir, rol_de

log = logging.getLogger(__name__)
CACHE_SEGUNDOS = 600
DIAS_SIN_FIRMA = 14
DIAS_EVALUACIONES = 7
DIAS_PME = 14
MODELO_IA = "claude-opus-5-5"
ORDEN = {"danger": 0, "warning": 1, "info": 2, "success": 3}
R = Perfil.Rol
DIAS = ["", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _aviso(nivel, icono, titulo, detalle="", url="", grupo="Seguimiento"):
    return {"nivel": nivel, "icono": icono, "titulo": titulo, "detalle": detalle, "url": url, "grupo": grupo}


def _plural(n, singular, plural=None):
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


# ---------------------------------------------------------------- reglas por función

def _calendario(user, hoy):
    from .calendario import items_del_periodo

    avisos = []
    siguiente = hoy + datetime.timedelta(days=1)
    while siguiente.isoweekday() > 5:  # viernes y fin de semana: avisa lo del próximo día hábil
        siguiente += datetime.timedelta(days=1)
    items = items_del_periodo(user, hoy, siguiente)
    dias = [(hoy + datetime.timedelta(days=i)) for i in range((siguiente - hoy).days + 1)]
    for dia in dias:
        delta = (dia - hoy).days
        nombre = "Hoy" if delta == 0 else "Mañana" if delta == 1 else f"El {DIAS[dia.isoweekday()]} {dia.day}"
        for x in items.get(dia, []):
            if x["tipo"] in ("Evaluación", "Plazo PME"):  # ya están en el seguimiento
                continue
            hora = f" a las {x['hora']:%H:%M}" if x.get("hora") else ""
            avisos.append(_aviso("info" if dia > hoy else "warning", "bi-calendar-event",
                                 f"{nombre}{hora}: {x['titulo']}", x["tipo"], f"/calendario/?mes={dia:%Y-%m}",
                                 "Calendario"))
    return avisos


def _docente(user, hoy, ahora):
    from .alertas import baja_asistencia, notas_pendientes
    from .libro import curso_usa_libro

    avisos = []
    acs = list(AsignaturaCurso.objects.filter(profesor=user, curso__anio=anio_actual())
               .select_related("curso__nivel", "asignatura"))
    if acs:
        dia = hoy.isoweekday()
        if dia <= 5:
            registradas = set(Clase.objects.filter(asignatura_curso__in=acs, fecha=hoy)
                              .values_list("asignatura_curso_id", flat=True))
            primeras = {}
            for h in (HorarioClase.objects.filter(asignatura_curso__in=acs, dia=dia).select_related("bloque")
                      .order_by("bloque__numero")):
                primeras.setdefault(h.asignatura_curso_id, h.bloque)
            faltan = [(ac, primeras[ac.pk]) for ac in acs if ac.pk in primeras and ac.pk not in registradas
                      and curso_usa_libro(ac.curso)]
            if faltan:
                vencidas = [p for p in faltan if p[1].inicio <= ahora]
                detalle = " · ".join(f"{ac.curso.nombre_corto} {ac.asignatura.nombre} ({b.inicio:%H:%M})" for ac, b in faltan)
                ac0 = faltan[0][0]
                avisos.append(_aviso("warning" if vencidas else "info", "bi-journal-text",
                                     f"Hoy: {_plural(len(faltan), 'clase')} del horario sin registrar en el libro",
                                     detalle, reverse("clase_crear", args=[ac0.pk])))
        desde = hoy - datetime.timedelta(days=DIAS_SIN_FIRMA)
        pasadas = Clase.objects.filter(asignatura_curso__in=acs, fecha__gte=desde, fecha__lt=hoy)
        sin_asistencia = pasadas.filter(asistencia_registrada=False).count()
        sin_firma = pasadas.filter(asistencia_registrada=True, firmada_en__isnull=True).count()
        if sin_asistencia:
            avisos.append(_aviso("danger", "bi-person-check", f"{_plural(sin_asistencia, 'clase')} de las últimas dos "
                                 "semanas sin asistencia registrada", "La asistencia del libro es la que se informa a SIGE.",
                                 reverse("libro")))
        if sin_firma:
            avisos.append(_aviso("warning", "bi-pen", f"{_plural(sin_firma, 'clase')} realizada{'s' if sin_firma > 1 else ''}"
                                 " sin firmar", "Firme el registro de cada clase en el libro.", reverse("libro")))
        proximas = list(Evaluacion.objects.filter(asignatura_curso__in=acs, fecha__gte=hoy,
                                                  fecha__lte=hoy + datetime.timedelta(days=DIAS_EVALUACIONES))
                        .select_related("asignatura_curso__curso__nivel", "asignatura_curso__asignatura"))
        if proximas:
            avisos.append(_aviso("info", "bi-clipboard-check",
                                 f"{_plural(len(proximas), 'evaluación', 'evaluaciones')} en los próximos 7 días",
                                 " · ".join(f"{e.fecha:%d/%m} {e.asignatura_curso.curso.nombre_corto} {e.nombre}" for e in proximas),
                                 reverse("libro_notas", args=[proximas[0].asignatura_curso_id])))
        cursos = list({ac.curso for ac in acs})
        mias = [x for prof, lista in notas_pendientes(cursos, hoy) if prof == user for x in lista]
        if mias:
            avisos.append(_aviso("warning", "bi-exclamation-diamond",
                                 f"{_plural(len(mias), 'asignatura')} con notas pendientes",
                                 " · ".join(f"{x['ac'].curso.nombre_corto} {x['ac'].asignatura.nombre}: {x['motivos'][0]}" for x in mias[:4]),
                                 reverse("libro_notas", args=[mias[0]["ac"].pk])))
            if hoy.month in (6, 7, 11, 12):
                avisos.append(_aviso("info", "bi-lightbulb", "Se acerca el cierre del semestre",
                                     "Ponga al día las notas pendientes antes de emitir informes y actas.",
                                     reverse("libro_notas", args=[mias[0]["ac"].pk]), "Sugerencia"))
    jefaturas = list(Curso.objects.filter(profesor_jefe=user, anio=anio_actual()).select_related("nivel"))
    if jefaturas:
        filas = baja_asistencia(jefaturas, hoy)
        riesgo = sum(1 for f in filas if f["riesgo"])
        seguidas = sum(1 for f in filas if f["seguidas"])
        if riesgo or seguidas:
            partes = []
            if riesgo:
                partes.append(f"{_plural(riesgo, 'estudiante')} bajo 85 % de asistencia (riesgo de repitencia)")
            if seguidas:
                partes.append(f"{_plural(seguidas, 'estudiante')} con 3 o más inasistencias seguidas")
            avisos.append(_aviso("danger" if riesgo else "warning", "bi-people",
                                 f"Su jefatura ({', '.join(c.nombre_corto for c in jefaturas)}) tiene estudiantes en alerta",
                                 " · ".join(partes) + ". Considere contactar a los apoderados.",
                                 reverse("alertas") + "?ver=asistencia"))
    return avisos


def _gestion(user, rol, hoy, ahora):
    from .alertas import baja_asistencia, notas_pendientes
    from .asistencia_personal import puede_registrar, puede_ver
    from .calendario import publica_eventos

    avisos = []
    est = Establecimiento.actual()
    cursos = list(Curso.objects.filter(anio=anio_actual()).select_related("nivel"))
    if rol in (R.DIRECTOR, R.UTP, R.ADMIN) or user.is_superuser:
        n = sum(len(v) for _, v in notas_pendientes(cursos, hoy))
        if n:
            avisos.append(_aviso("warning", "bi-exclamation-diamond", f"{_plural(n, 'asignatura')} con notas pendientes",
                                 "Profesores sin notas recientes o con evaluaciones aplicadas sin registrar.",
                                 reverse("alertas")))
        sin_firma = Clase.objects.filter(fecha__gte=hoy - datetime.timedelta(days=7), fecha__lt=hoy,
                                         asistencia_registrada=True, firmada_en__isnull=True).count()
        if sin_firma and rol in (R.UTP, R.DIRECTOR):
            avisos.append(_aviso("info", "bi-pen", f"{_plural(sin_firma, 'clase')} de la última semana sin firma docente",
                                 "Puede revisarlas y visarlas desde el libro de clases.", reverse("libro")))
    if es_gestion(user):
        pendientes = SolicitudCambio.objects.filter(estado=SolicitudCambio.Estado.PENDIENTE).count()
        if pendientes:
            avisos.append(_aviso("warning", "bi-inbox", f"{_plural(pendientes, 'solicitud', 'solicitudes')} de cambio de datos por revisar", "",
                                 reverse("solicitudes")))
    if rol in (R.DIRECTOR, R.INSPECTOR, R.CONVIVENCIA, R.ADMIN) or user.is_superuser:
        filas = baja_asistencia(cursos, hoy)
        riesgo = sum(1 for f in filas if f["riesgo"])
        seguidas = sum(1 for f in filas if f["seguidas"])
        if riesgo or seguidas:
            partes = []
            if riesgo:
                partes.append(f"{_plural(riesgo, 'estudiante')} bajo 85 % (riesgo de repitencia)")
            if seguidas:
                partes.append(f"{_plural(seguidas, 'estudiante')} con 3 o más inasistencias seguidas")
            avisos.append(_aviso("danger" if riesgo else "warning", "bi-people", "Estudiantes con alerta de asistencia",
                                 " · ".join(partes) + ".", reverse("alertas") + "?ver=asistencia"))
    if rol in (R.CONVIVENCIA, R.DIRECTOR) or user.is_superuser:
        derivadas = Anotacion.objects.filter(derivada=True, estado_derivacion__in=["", EstadoDerivacion.PENDIENTE]).count()
        if derivadas:
            avisos.append(_aviso("warning", "bi-shield-exclamation", f"{_plural(derivadas, 'derivación', 'derivaciones')} "
                                 "a Convivencia pendiente" + ("s" if derivadas > 1 else "") + " de revisión", "",
                                 reverse("convivencia")))
    if est.pk and est.tiene_modulo("asistencia_personal") and puede_registrar(user) and hoy.isoweekday() <= 5:
        if (ahora >= datetime.time(9, 0) and Funcionario.objects.filter(activo=True).exists()
                and not AsistenciaFuncionario.objects.filter(fecha=hoy).exists()):
            avisos.append(_aviso("warning", "bi-person-badge", "Aún no se registra la asistencia del personal de hoy",
                                 "", reverse("asistencia_personal")))
    if est.pk and est.tiene_modulo("sep") and puede_ver(user):
        acciones = AccionPME.objects.filter(plan__anio=anio_actual()).exclude(estado=AccionPME.Estado.EJECUTADA)
        atrasadas = [a for a in acciones if a.atrasada]
        por_vencer = acciones.filter(termino__gte=hoy, termino__lte=hoy + datetime.timedelta(days=DIAS_PME)).count()
        if atrasadas:
            avisos.append(_aviso("danger", "bi-clipboard-data", f"{_plural(len(atrasadas), 'acción', 'acciones')} del PME "
                                 "con plazo vencido", " · ".join(a.nombre for a in atrasadas[:3]), reverse("pme")))
        if por_vencer:
            avisos.append(_aviso("info", "bi-clipboard-data", f"{_plural(por_vencer, 'acción', 'acciones')} del PME vence"
                                 + ("n" if por_vencer > 1 else "") + " en las próximas dos semanas", "", reverse("pme")))
    if publica_eventos(user):
        from .models import EventoCalendario

        if not EventoCalendario.objects.filter(fecha__gte=hoy, fecha__lte=hoy + datetime.timedelta(days=14),
                                               privado=False).exists():
            avisos.append(_aviso("info", "bi-lightbulb", "No hay eventos en el calendario para las próximas dos semanas",
                                 "Agende consejos, reuniones de apoderados y plazos: cada persona recibirá el aviso el día "
                                 "anterior y el mismo día.", reverse("calendario"), "Sugerencia"))
    return avisos


def _sostenedor(user, perfil, hoy):
    from .tenencia import en_establecimiento

    avisos = []
    for est in Establecimiento.objects.filter(sostenedor=perfil.sostenedor, activo=True).order_by("nombre"):
        with en_establecimiento(est):
            partes = []
            atrasadas = [a for a in AccionPME.objects.filter(plan__anio=anio_actual())
                         .exclude(estado=AccionPME.Estado.EJECUTADA) if a.atrasada]
            if atrasadas:
                partes.append(f"{_plural(len(atrasadas), 'acción', 'acciones')} PME vencida{'s' if len(atrasadas) > 1 else ''}")
            if (hoy.isoweekday() <= 5 and Funcionario.objects.filter(activo=True).exists()
                    and not AsistenciaFuncionario.objects.filter(fecha=hoy).exists()):
                partes.append("asistencia del personal de hoy sin registrar")
        if partes:
            avisos.append(_aviso("danger" if atrasadas else "warning", "bi-building", est.nombre, " · ".join(partes),
                                 reverse("red")))
    return avisos


def calcular(user, hoy=None, ahora=None):
    """Lista de avisos del usuario, ordenada por prioridad."""
    hoy = hoy or timezone.localdate()
    ahora = ahora or timezone.localtime().time()
    perfil = _perfil(user)
    rol = rol_de(user)
    if rol == R.SUPERADMIN:
        return []
    from .tenencia import establecimiento_actual

    if establecimiento_actual() is None:
        if perfil and perfil.de_sostenedor:
            return _sostenedor(user, perfil, hoy)
        if Establecimiento.actual().pk is None:
            return []
    avisos = _calendario(user, hoy)
    avisos += _docente(user, hoy, ahora)
    if rol != R.PROFESOR or user.is_superuser:
        avisos += _gestion(user, rol, hoy, ahora)
    avisos.sort(key=lambda a: (a["grupo"] == "Sugerencia", ORDEN.get(a["nivel"], 9)))
    return avisos


def avisos_de(request):
    """Avisos del usuario con caché de unos minutos en la sesión (se recalculan tras cualquier cambio)."""
    est = getattr(request, "establecimiento", None)
    clave = f"{est.pk if est else 0}-{timezone.localdate().isoformat()}"
    guardado = request.session.get("asistente")
    if guardado and guardado.get("clave") == clave and time.time() - guardado.get("t", 0) < CACHE_SEGUNDOS:
        return guardado["avisos"]
    try:
        avisos = calcular(request.user)
    except Exception:  # el asistente nunca debe impedir usar la plataforma
        log.exception("No se pudieron calcular los avisos del asistente")
        avisos = []
    request.session["asistente"] = {"clave": clave, "t": time.time(), "avisos": avisos}
    return avisos


class AsistenteMiddleware:
    """Tras guardar algo (POST), los avisos se recalculan en la siguiente página."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and hasattr(request, "session"):
            request.session.pop("asistente", None)
        return self.get_response(request)


# ---------------------------------------------------------------- IA opcional

def ia_disponible(est):
    return bool(est and est.pk and est.asistente_ia and os.environ.get("ANTHROPIC_API_KEY"))


def _texto_para_ia(user, avisos, hoy):
    rol = Perfil.Rol(rol_de(user)).label
    lineas = [f"- [{a['grupo']} · prioridad {a['nivel']}] {a['titulo']}" + (f": {a['detalle']}" if a["detalle"] else "")
              for a in avisos]
    return (f"Fecha: {hoy:%d/%m/%Y}. Rol del usuario: {rol}.\n"
            "Avisos de seguimiento generados hoy por la plataforma:\n" + ("\n".join(lineas) or "- (sin avisos)"))


SISTEMA_IA = (
    "Eres el asistente de Pupitre, una plataforma de gestión curricular para establecimientos escolares chilenos. "
    "A partir de los avisos del día que te entrega la plataforma, sugiere al usuario qué hacer primero y cómo, "
    "considerando las funciones de su rol y la normativa escolar chilena (Decreto 67 de evaluación, asistencia mínima "
    "de 85 %, PME/SEP, Estatuto Docente) solo cuando sea pertinente. Responde en español de Chile, con un tono cordial "
    "y directo, en 3 a 5 viñetas breves ordenadas por prioridad, más una frase final de ánimo. No inventes datos que no "
    "estén en los avisos ni pidas datos personales de estudiantes.")


def consultar_ia(sistema, contenido, error_rechazo="La IA no pudo responder.", max_tokens=16000):
    """Llama a Claude con un prompt de sistema y un texto. Devuelve (texto, error)."""
    try:
        import anthropic
    except ImportError:
        return "", "Falta instalar la librería «anthropic» en el servidor."
    client = anthropic.Anthropic(timeout=120.0)
    try:
        respuesta = client.beta.messages.create(
            model=MODELO_IA, max_tokens=max_tokens, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "low"}, system=sistema,
            messages=[{"role": "user", "content": contenido}])
    except anthropic.AuthenticationError:
        return "", "La clave de la IA no es válida. Revise ANTHROPIC_API_KEY en el servidor."
    except anthropic.RateLimitError:
        return "", "La IA está con mucha demanda. Intente de nuevo en unos minutos."
    except anthropic.APIConnectionError:
        return "", "No se pudo conectar con el servicio de IA."
    except anthropic.APIStatusError as e:
        log.warning("Error de la API de IA: %s", e)
        return "", "El servicio de IA respondió con un error. Intente más tarde."
    if respuesta.stop_reason == "refusal":
        return "", error_rechazo
    return "\n".join(b.text for b in respuesta.content if b.type == "text").strip(), ""


def sugerencias_ia(user, avisos, hoy=None):
    """Pide a Claude sugerencias a partir de los avisos. Devuelve (texto, error)."""
    hoy = hoy or timezone.localdate()
    return consultar_ia(SISTEMA_IA, _texto_para_ia(user, avisos, hoy), "La IA no pudo generar sugerencias para estos avisos.")


# ---------------------------------------------------------------- vistas

@login_required
def asistente(request):
    est = getattr(request, "establecimiento", None)
    avisos = calcular(request.user)
    request.session["asistente"] = {"clave": f"{est.pk if est else 0}-{timezone.localdate().isoformat()}",
                                    "t": time.time(), "avisos": avisos}
    grupos = {}
    for a in avisos:
        grupos.setdefault(a["grupo"], []).append(a)
    ia = request.session.get("asistente_ia")
    if ia and ia.get("fecha") != timezone.localdate().isoformat():
        ia = None
    return render(request, "academico/asistente.html", {
        "grupos": grupos, "n": len(avisos), "ia_disponible": ia_disponible(est), "ia": ia,
        "ia_configurable": bool(est and est.pk) and es_gestion(request.user),
        "ia_activada": bool(est and est.pk and est.asistente_ia), "clave_ia": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@login_required
@require_POST
def asistente_ia(request):
    est = getattr(request, "establecimiento", None)
    exigir(ia_disponible(est))
    texto, error = sugerencias_ia(request.user, calcular(request.user))
    if error:
        messages.error(request, error)
    else:
        request.session["asistente_ia"] = {"fecha": timezone.localdate().isoformat(), "texto": texto,
                                           "hora": timezone.localtime().strftime("%H:%M")}
    return redirect("asistente")
