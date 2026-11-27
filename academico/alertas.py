"""Alertas de gestión: profesores sin notas, bajo rendimiento y baja asistencia.

Las ven UTP, Dirección, Inspectoría General, Convivencia Escolar y el sostenedor (todo el establecimiento);
el profesor(a) jefe ve las de su curso.
"""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import render
from django.utils import timezone

from .calculos import ASISTENCIA_MINIMA, resumen_curso
from .models import AsignaturaCurso, Curso, Evaluacion, Perfil, anio_actual
from .permisos import _perfil, es_gestion, exigir

DIAS_SIN_NOTAS = 45
NOTA_ROJA = Decimal("4.0")
ASISTENCIA_ALERTA = Decimal("90")
AUSENCIAS_SEGUIDAS = 3
ROLES_ALERTAS = {Perfil.Rol.DIRECTOR, Perfil.Rol.UTP, Perfil.Rol.INSPECTOR, Perfil.Rol.CONVIVENCIA,
                 Perfil.Rol.SOSTENEDOR, Perfil.Rol.SUPERADMIN}


def ve_todas_las_alertas(user):
    perfil = _perfil(user)
    return es_gestion(user) or bool(perfil and perfil.rol in ROLES_ALERTAS)


def ve_alertas(user):
    return ve_todas_las_alertas(user) or Curso.objects.filter(profesor_jefe=user, anio=anio_actual()).exists()


def cursos_de_alertas(user):
    qs = Curso.objects.filter(anio=anio_actual()).select_related("nivel", "profesor_jefe")
    if not ve_todas_las_alertas(user):
        qs = qs.filter(profesor_jefe=user)
    return list(qs.order_by("nivel__orden", "letra"))


def notas_pendientes(cursos, hoy=None):
    """Asignaturas sin notas en el semestre o sin calificaciones nuevas hace más de DIAS_SIN_NOTAS días."""
    hoy = hoy or timezone.localdate()
    semestre = 1 if hoy.month < 7 else 2
    inicio_semestre = datetime.date(hoy.year, 3, 1) if semestre == 1 else datetime.date(hoy.year, 7, 20)
    acs = (AsignaturaCurso.objects.filter(curso__in=cursos)
           .select_related("curso__nivel", "asignatura", "profesor")
           .annotate(n_eval=Count("evaluaciones", distinct=True),
                     ultima=Max("evaluaciones__fecha")))
    con_notas_semestre = set(
        Evaluacion.objects.filter(asignatura_curso__curso__in=cursos, semestre=semestre, calificaciones__isnull=False)
        .values_list("asignatura_curso_id", flat=True).distinct())
    # evaluaciones ya aplicadas (fecha pasada) con notas incompletas
    incompletas = defaultdict(list)
    for ev in (Evaluacion.objects.filter(asignatura_curso__curso__in=cursos, fecha__lt=hoy, fecha__gte=inicio_semestre)
               .annotate(n=Count("calificaciones")).select_related("asignatura_curso__asignatura")):
        if ev.n == 0:
            incompletas[ev.asignatura_curso_id].append(ev)
    por_profesor = defaultdict(list)
    for ac in acs:
        motivos = []
        if hoy >= inicio_semestre + datetime.timedelta(days=DIAS_SIN_NOTAS) and ac.id not in con_notas_semestre:
            motivos.append(f"sin notas en el {semestre}° semestre")
        elif ac.ultima and (hoy - ac.ultima).days > DIAS_SIN_NOTAS and ac.id in con_notas_semestre:
            motivos.append(f"última evaluación hace {(hoy - ac.ultima).days} días")
        for ev in incompletas.get(ac.id, []):
            motivos.append(f"«{ev.nombre}» ({ev.fecha:%d/%m}) aplicada y sin notas registradas")
        if motivos:
            por_profesor[ac.profesor].append({"ac": ac, "motivos": motivos})
    return sorted(por_profesor.items(), key=lambda par: (par[0] is None, par[0] and par[0].last_name or ""))


def bajo_rendimiento(cursos):
    """Estudiantes con asignaturas bajo 4,0 o en riesgo de repitencia."""
    filas = []
    for curso in cursos:
        _, _, resumenes = resumen_curso(curso)
        for r in resumenes:
            rojas = [f for f in r.asignaturas if f.aplica and f.final is not None and f.final < NOTA_ROJA]
            if not rojas and not (r.promedio_general is not None and r.promedio_general < Decimal("5.0")
                                  and len(r.reprobadas) >= 2):
                continue
            riesgo = r.situacion == "Reprobado(a)"
            filas.append({"est": r.estudiante, "curso": curso, "rojas": rojas, "promedio": r.promedio_general,
                          "riesgo": riesgo, "situacion": r.situacion})
    filas.sort(key=lambda f: (not f["riesgo"], -len(f["rojas"]), f["promedio"] or 0))
    return filas


def baja_asistencia(cursos, hoy=None):
    """% anual bajo 90 (alerta) o bajo 85 (riesgo de repitencia) y ausencias seguidas recientes del libro."""
    from .libro import asistencia_diaria

    hoy = hoy or timezone.localdate()
    filas = []
    for curso in cursos:
        diario = asistencia_diaria(curso, hoy - datetime.timedelta(days=30), hoy)
        dias = sorted({f for _, f in diario})
        for est in curso.estudiantes.filter(activo=True):
            seguidas = maximo = 0
            for d in dias:
                estado = diario.get((est.id, d))
                if estado == "A":
                    seguidas += 1
                    maximo = max(maximo, seguidas)
                elif estado:
                    seguidas = 0
            pct = est.porcentaje_asistencia
            bajo = pct is not None and pct < ASISTENCIA_ALERTA
            if bajo or maximo >= AUSENCIAS_SEGUIDAS:
                filas.append({"est": est, "curso": curso, "pct": pct, "riesgo": pct is not None and pct < ASISTENCIA_MINIMA,
                              "seguidas": maximo if maximo >= AUSENCIAS_SEGUIDAS else 0,
                              "ausente_hoy": bool(dias) and dias[-1] == hoy and diario.get((est.id, hoy)) == "A"})
    filas.sort(key=lambda f: (not f["riesgo"], -(f["seguidas"]), f["pct"] if f["pct"] is not None else 100))
    return filas


@login_required
def alertas(request):
    exigir(ve_alertas(request.user))
    cursos = cursos_de_alertas(request.user)
    pendientes = notas_pendientes(cursos)
    rendimiento = bajo_rendimiento(cursos)
    asistencia = baja_asistencia(cursos)
    pestana = request.GET.get("ver", "notas")
    return render(request, "academico/alertas.html", {
        "pendientes": pendientes, "n_pendientes": sum(len(v) for _, v in pendientes),
        "rendimiento": rendimiento, "asistencia": asistencia, "pestana": pestana,
        "todas": ve_todas_las_alertas(request.user), "umbral": ASISTENCIA_ALERTA, "minimo": ASISTENCIA_MINIMA,
        "dias": DIAS_SIN_NOTAS,
        "n_riesgo_notas": sum(1 for f in rendimiento if f["riesgo"]),
        "n_riesgo_asist": sum(1 for f in asistencia if f["riesgo"]),
    })
