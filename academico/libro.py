"""Libro de clases digital: leccionario (planificación clase a clase), asistencia y firma docente.

Alimenta al resto de la plataforma:
- Una clase marcada «de evaluación» crea la evaluación en el libro de notas de la asignatura.
- La asistencia registrada recalcula el % de asistencia anual del estudiante, que usan los informes,
  el certificado y la situación final (Decreto 67: 85 % mínimo).
"""
import calendar
import datetime
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.http import JsonResponse

from . import curriculo
from .forms import ClaseForm, ObjetivoForm, VisadoForm
from .models import (
    GRADOS_CURRICULUM, AsignaturaCurso, Establecimiento, AsistenciaClase, Clase, Curso, Estudiante, Evaluacion, ObjetivoAprendizaje,
    anio_actual,
)
from .permisos import (
    asignaturas_curso_visibles, es_gestion, es_solo_lectura, exigir, puede_editar_notas, puede_ver_asignatura_curso,
    puede_ver_informe_curso,
)

ESTADOS = AsistenciaClase.Estado
NOMBRES_MES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre"]


# --------------------------------------------------------------------------- reglas

def semestre_de(fecha):
    """En Chile el 2° semestre comienza después de las vacaciones de invierno (julio)."""
    return 1 if fecha.month < 7 else 2


def estudiantes_de(ac):
    """Estudiantes activos del curso que cursan la asignatura (p. ej. Religión según su opción)."""
    return [e for e in ac.curso.estudiantes.filter(activo=True) if e.cursa(ac.asignatura)]


def asistencia_diaria(curso, desde=None, hasta=None):
    """{(estudiante_id, fecha): estado} tomando, para cada día, la primera clase registrada de ese estudiante.

    Es la asistencia diaria que exige la normativa (se pasa en la primera hora). Atrasos y retiros cuentan
    como asistencia; solo la ausencia la descuenta.
    """
    qs = AsistenciaClase.objects.filter(clase__asignatura_curso__curso=curso, clase__asistencia_registrada=True)
    if desde:
        qs = qs.filter(clase__fecha__gte=desde)
    if hasta:
        qs = qs.filter(clase__fecha__lte=hasta)
    qs = qs.order_by("clase__fecha", F("clase__hora_inicio").asc(nulls_last=True), "clase_id")
    diario = {}
    for est_id, fecha, estado in qs.values_list("estudiante_id", "clase__fecha", "estado"):
        diario.setdefault((est_id, fecha), estado)
    return diario


def recalcular_asistencia(curso):
    """Actualiza el % de asistencia anual de los estudiantes del curso a partir del libro de clases."""
    conteo = defaultdict(lambda: [0, 0])
    for (est_id, _), estado in asistencia_diaria(curso).items():
        conteo[est_id][1] += 1
        if estado != ESTADOS.AUSENTE:
            conteo[est_id][0] += 1
    for est_id, (presentes, dias) in conteo.items():
        pct = (Decimal(presentes * 100) / Decimal(dias)).quantize(Decimal("0.1"))
        Estudiante.objects.filter(pk=est_id).update(porcentaje_asistencia=pct)
    return len(conteo)


def curso_usa_libro(curso):
    return Clase.objects.filter(asignatura_curso__curso=curso, asistencia_registrada=True).exists()


def _sincronizar_evaluacion(request, clase, datos):
    """Crea, actualiza o desvincula la evaluación asociada a la clase."""
    ev = clase.evaluacion
    if datos.get("es_evaluacion"):
        if ev is None:
            ev = Evaluacion(asignatura_curso=clase.asignatura_curso)
        ev.nombre = datos["nombre_evaluacion"].strip()
        ev.fecha = clase.fecha
        ev.semestre = semestre_de(clase.fecha)
        ev.ponderacion = datos.get("ponderacion") or Decimal("1")
        ev.save()
        if clase.evaluacion_id != ev.pk:
            clase.evaluacion = ev
            clase.save(update_fields=["evaluacion"])
    elif ev is not None:
        if ev.calificaciones.exists():
            messages.warning(request, f"La evaluación «{ev.nombre}» ya tiene notas: se mantiene en el libro de notas.")
        else:
            clase.evaluacion = None
            clase.save(update_fields=["evaluacion"])
            ev.delete()


# --------------------------------------------------------------------------- vistas

@login_required
def libro(request):
    """Entrada del menú: las asignaturas del usuario y los libros de curso que puede ver."""
    acs = (asignaturas_curso_visibles(request.user).filter(curso__anio=anio_actual())
           .annotate(n_clases=Count("clases", distinct=True),
                     n_firmadas=Count("clases", filter=Q(clases__firmada_en__isnull=False), distinct=True))
           .order_by("curso__nivel__orden", "curso__letra", "asignatura__orden", "asignatura__nombre"))
    propias = [ac for ac in acs if ac.profesor_id == request.user.id]
    por_curso = defaultdict(list)
    for ac in acs:
        por_curso[ac.curso].append(ac)
    cursos = [c for c in por_curso if puede_ver_informe_curso(request.user, c)]
    hoy = timezone.localdate()
    pendientes = (Clase.objects.filter(asignatura_curso__in=propias, fecha__lte=hoy, firmada_en__isnull=True)
                  .select_related("asignatura_curso__curso__nivel", "asignatura_curso__asignatura")
                  .order_by("-fecha")[:10])
    return render(request, "academico/libro.html", {
        "propias": propias, "por_curso": dict(por_curso), "cursos": cursos, "pendientes": pendientes,
    })


@login_required
def leccionario(request, ac_pk):
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor"), pk=ac_pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    clases = list(ac.clases.select_related("evaluacion", "firmada_por")
                  .annotate(ausentes=Count("asistencias", filter=Q(asistencias__estado=ESTADOS.AUSENTE)))
                  .order_by("-fecha", "-hora_inicio", "-id"))
    hoy = timezone.localdate()
    horas = sum(c.bloques for c in clases if c.asistencia_registrada)
    return render(request, "academico/leccionario.html", {
        "ac": ac, "clases": clases, "editable": puede_editar_notas(request.user, ac), "hoy": hoy,
        "horas_realizadas": horas, "n_firmadas": sum(1 for c in clases if c.firmada),
        "n_planificadas": sum(1 for c in clases if c.fecha > hoy),
    })


@login_required
def clase_form(request, ac_pk=None, pk=None):
    if pk:
        clase = get_object_or_404(Clase.objects.select_related("asignatura_curso__curso", "evaluacion"), pk=pk)
        ac = clase.asignatura_curso
    else:
        ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso", "asignatura"), pk=ac_pk)
        ultima = ac.clases.order_by("-fecha", "-id").first()
        clase = Clase(asignatura_curso=ac, bloques=ultima.bloques if ultima else 2,
                      hora_inicio=ultima.hora_inicio if ultima else None,
                      unidad=ultima.unidad if ultima else "")
        if request.GET.get("fecha"):
            try:
                clase.fecha = datetime.date.fromisoformat(request.GET["fecha"])
            except ValueError:
                pass
    exigir(puede_editar_notas(request.user, ac) and not es_solo_lectura(request.user))
    if clase.firmada:
        messages.warning(request, "La clase ya está firmada y no se puede modificar.")
        return redirect("clase_detalle", pk=clase.pk)
    oas = curriculo.oas_para(ac)
    inicial = {}
    if not pk and request.GET.get("evaluacion"):
        inicial = {"es_evaluacion": True, "nombre_evaluacion": request.GET["evaluacion"][:100]}
        if request.GET.get("objetivo"):
            inicial["objetivo"] = request.GET["objetivo"][:2000]
    form = ClaseForm(request.POST or None, instance=clase, oas=oas, initial=inicial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            clase = form.save(commit=False)
            if not clase.pk:
                clase.creada_por = request.user
            clase.save()
            form.save_m2m()
            _sincronizar_evaluacion(request, clase, form.cleaned_data)
        messages.success(request, "Clase guardada en el leccionario.")
        return redirect("clase_detalle", pk=clase.pk)
    return render(request, "academico/clase_form.html", {
        "form": form, "ac": ac, "clase": clase, "hay_oas": oas.exists(),
        "grado_txt": dict(GRADOS_CURRICULUM).get(curriculo.grado_de_curso(ac.curso), ""),
        "titulo": f"{'Editar' if pk else 'Planificar'} clase – {ac.asignatura} · {ac.curso.nombre_corto}",
    })


@login_required
def clase_detalle(request, pk):
    """Registro de la clase: lo planificado, la asistencia, la firma del docente y la observación de UTP."""
    clase = get_object_or_404(
        Clase.objects.select_related("asignatura_curso__curso__nivel", "asignatura_curso__asignatura",
                                     "asignatura_curso__profesor", "evaluacion", "firmada_por"), pk=pk)
    ac = clase.asignatura_curso
    exigir(puede_ver_asignatura_curso(request.user, ac))
    editable = puede_editar_notas(request.user, ac) and not es_solo_lectura(request.user)
    gestion = es_gestion(request.user)
    hoy = timezone.localdate()
    estudiantes = estudiantes_de(ac)
    registro = {a.estudiante_id: a.estado for a in clase.asistencias.all()}
    visado = VisadoForm(instance=clase, prefix="v")

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "visado":
            exigir(gestion and not es_solo_lectura(request.user))
            visado = VisadoForm(request.POST, instance=clase, prefix="v")
            if visado.is_valid():
                visado.save()
                messages.success(request, "Observación de UTP guardada.")
                return redirect("clase_detalle", pk=clase.pk)
        elif accion == "reabrir":
            exigir(gestion and not es_solo_lectura(request.user) and clase.firmada)
            nota = (f"Reabierta para corrección por {request.user.get_full_name() or request.user.username} "
                    f"el {timezone.localtime():%d-%m-%Y %H:%M}.")
            clase.visado_utp = f"{clase.visado_utp}\n{nota}".strip()
            clase.firmada_en = None
            clase.firmada_por = None
            clase.save(update_fields=["visado_utp", "firmada_en", "firmada_por"])
            messages.success(request, "La clase quedó abierta: el docente puede corregirla y volver a firmarla.")
            return redirect("clase_detalle", pk=clase.pk)
        else:
            exigir(editable)
            if clase.firmada:
                messages.error(request, "La clase ya está firmada y no se puede modificar.")
                return redirect("clase_detalle", pk=clase.pk)
            if clase.fecha > hoy:
                messages.error(request, "No se puede registrar asistencia de una clase futura.")
                return redirect("clase_detalle", pk=clase.pk)
            validos = {e.value for e in ESTADOS}
            with transaction.atomic():
                for est in estudiantes:
                    estado = request.POST.get(f"a_{est.id}", ESTADOS.PRESENTE)
                    if estado not in validos:
                        estado = ESTADOS.PRESENTE
                    AsistenciaClase.objects.update_or_create(clase=clase, estudiante=est, defaults={"estado": estado})
                clase.asistencia_registrada = True
                campos = ["asistencia_registrada"]
                if "observaciones" in request.POST:
                    clase.observaciones = request.POST["observaciones"].strip()
                    campos.append("observaciones")
                if accion == "firmar":
                    if not request.user.check_password(request.POST.get("clave", "")):
                        transaction.set_rollback(True)
                        messages.error(request, "Contraseña incorrecta: la clase no se firmó. La asistencia tampoco se guardó.")
                        return redirect("clase_detalle", pk=clase.pk)
                    clase.firmada_por = request.user
                    clase.firmada_en = timezone.now()
                    campos += ["firmada_por", "firmada_en"]
                clase.save(update_fields=campos)
                recalcular_asistencia(ac.curso)
            ausentes = sum(1 for est in estudiantes if request.POST.get(f"a_{est.id}") == ESTADOS.AUSENTE)
            if accion == "firmar":
                messages.success(request, f"Clase firmada. Asistencia registrada ({ausentes} ausente(s)).")
            else:
                messages.success(request, f"Asistencia guardada ({ausentes} ausente(s)). Recuerde firmar la clase.")
            return redirect("clase_detalle", pk=clase.pk)

    filas = [(e, registro.get(e.id, ESTADOS.PRESENTE if not clase.asistencia_registrada else "")) for e in estudiantes]
    anterior = ac.clases.filter(Q(fecha__lt=clase.fecha) | Q(fecha=clase.fecha, id__lt=clase.id)).order_by("-fecha", "-id").first()
    siguiente = ac.clases.filter(Q(fecha__gt=clase.fecha) | Q(fecha=clase.fecha, id__gt=clase.id)).order_by("fecha", "id").first()
    return render(request, "academico/clase_detalle.html", {
        "clase": clase, "ac": ac, "filas": filas, "estados": ESTADOS.choices, "editable": editable,
        "gestion": gestion and not es_solo_lectura(request.user), "visado": visado, "futura": clase.fecha > hoy,
        "anterior": anterior, "siguiente": siguiente,
        "resumen": {k: sum(1 for _, v in filas if v == k) for k, _ in ESTADOS.choices},
    })


@login_required
@require_POST
def clase_eliminar(request, pk):
    clase = get_object_or_404(Clase, pk=pk)
    ac = clase.asignatura_curso
    exigir(puede_editar_notas(request.user, ac) and not es_solo_lectura(request.user))
    if clase.firmada:
        messages.error(request, "Una clase firmada no se puede eliminar.")
        return redirect("clase_detalle", pk=clase.pk)
    ev = clase.evaluacion
    with transaction.atomic():
        clase.delete()
        if ev is not None and not ev.calificaciones.exists():
            ev.delete()
        recalcular_asistencia(ac.curso)
    messages.success(request, "Clase eliminada del leccionario.")
    return redirect("leccionario", ac_pk=ac.pk)


def _mes(request, curso):
    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in request.GET.get("mes", "").split("-"))
        datetime.date(anio, mes, 1)
    except ValueError:
        anio, mes = (hoy.year, hoy.month) if hoy.year == curso.anio else (curso.anio, 12)
    return anio, mes


def datos_mes(curso, anio, mes):
    """Asistencia diaria del mes, clases del mes y totales por estudiante."""
    desde = datetime.date(anio, mes, 1)
    hasta = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])
    clases = list(Clase.objects.filter(asignatura_curso__curso=curso, fecha__range=(desde, hasta))
                  .select_related("asignatura_curso__asignatura", "asignatura_curso__profesor", "firmada_por",
                                  "evaluacion")
                  .order_by("fecha", F("hora_inicio").asc(nulls_last=True), "id"))
    diario = asistencia_diaria(curso, desde, hasta)
    dias = sorted({f for _, f in diario})
    estudiantes = list(curso.estudiantes.filter(activo=True))
    filas = []
    for est in estudiantes:
        celdas = [diario.get((est.id, d), "") for d in dias]
        registrados = [c for c in celdas if c]
        presentes = sum(1 for c in registrados if c != ESTADOS.AUSENTE)
        pct = round(presentes * 100 / len(registrados), 1) if registrados else None
        filas.append({"est": est, "celdas": celdas, "ausencias": len(registrados) - presentes,
                      "atrasos": celdas.count(ESTADOS.ATRASO), "pct": pct})
    return {"dias": dias, "filas": filas, "clases": clases, "desde": desde, "hasta": hasta}


@login_required
def libro_curso(request, pk):
    curso = get_object_or_404(Curso.objects.select_related("nivel", "profesor_jefe"), pk=pk)
    exigir(puede_ver_informe_curso(request.user, curso))
    anio, mes = _mes(request, curso)
    datos = datos_mes(curso, anio, mes)
    previo = datetime.date(anio, mes, 1) - datetime.timedelta(days=1)
    proximo = datetime.date(anio, mes, 28) + datetime.timedelta(days=4)
    return render(request, "academico/libro_curso.html", {
        "curso": curso, **datos, "mes_txt": f"{NOMBRES_MES[mes]} {anio}", "mes_param": f"{anio}-{mes:02d}",
        "previo": f"{previo.year}-{previo.month:02d}", "proximo": f"{proximo.year}-{proximo.month:02d}",
        "sin_firma": sum(1 for c in datos["clases"] if not c.firmada and c.fecha <= timezone.localdate()),
    })


def _pdf(contenido, nombre):
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


@login_required
def leccionario_pdf(request, ac_pk):
    from django.utils.text import slugify

    from .exportacion import pdf_leccionario

    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor"), pk=ac_pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    clases = list(ac.clases.select_related("firmada_por", "evaluacion")
                  .annotate(ausentes=Count("asistencias", filter=Q(asistencias__estado=ESTADOS.AUSENTE))))
    nombre = f"leccionario_{slugify(ac.asignatura.nombre)}_{slugify(ac.curso.nombre_corto)}.pdf"
    return _pdf(pdf_leccionario(ac, clases), nombre)


@login_required
def asistencia_mes_pdf(request, pk):
    from django.utils.text import slugify

    from .exportacion import pdf_asistencia_mes

    curso = get_object_or_404(Curso.objects.select_related("nivel", "profesor_jefe"), pk=pk)
    exigir(puede_ver_informe_curso(request.user, curso))
    anio, mes = _mes(request, curso)
    datos = datos_mes(curso, anio, mes)
    nombre = f"asistencia_{slugify(curso.nombre_corto)}_{anio}-{mes:02d}.pdf"
    return _pdf(pdf_asistencia_mes(curso, datos, f"{NOMBRES_MES[mes]} {anio}"), nombre)


# --------------------------------------------------------------------------- asistente de planificación

@login_required
def asistente_clase(request, ac_pk):
    """Propuesta de clase y evaluaciones para un OA (JSON, sin internet ni IA)."""
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura"), pk=ac_pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    texto = ""
    if request.GET.get("oa"):
        oa = get_object_or_404(curriculo.oas_para(ac), pk=request.GET["oa"])
        texto = f"OA {oa.numero}: {oa.texto}"
    texto = texto or request.GET.get("texto", "").strip()
    if not texto:
        return JsonResponse({"error": "Elija un OA o escriba el objetivo de la clase."}, status=400)
    try:
        bloques = max(1, min(6, int(request.GET.get("bloques") or 2)))
    except ValueError:
        bloques = 2
    propuesta = curriculo.proponer_clase(texto, curriculo.clave_asignatura(ac.asignatura.nombre), bloques)
    propuesta["objetivo"] = texto
    return JsonResponse(propuesta)


@login_required
def evaluacion_unidad(request, ac_pk):
    """Sugerencia de evaluación sumativa y formativas según lo planificado en el leccionario."""
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor"), pk=ac_pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    unidades = [u for u in ac.clases.order_by("fecha").values_list("unidad", flat=True).distinct() if u]
    unidades = list(dict.fromkeys(unidades))
    unidad = request.GET.get("unidad", unidades[-1] if unidades else "")
    propuesta = curriculo.evaluacion_de_unidad(ac, unidad or None)
    return render(request, "academico/evaluacion_unidad.html", {
        "ac": ac, "unidades": unidades, "unidad": unidad, "p": propuesta,
        "editable": puede_editar_notas(request.user, ac) and not es_solo_lectura(request.user),
        "nombre_sugerido": f"Evaluación {unidad}".strip() if unidad else "Evaluación sumativa",
        "objetivo_sugerido": (f"Evaluación sumativa ({propuesta['tipo'].lower()}) de: "
                              + "; ".join(f["oa"].split(":")[0] for f in propuesta["tabla"]))[:2000] if propuesta else "",
    })


@login_required
def curriculum(request):
    """Catálogo de OA: oficiales precargados y los propios del establecimiento."""
    qs = ObjetivoAprendizaje.disponibles()
    asig = request.GET.get("asignatura", "")
    grado = request.GET.get("grado", "")
    q = request.GET.get("q", "").strip()
    if asig:
        qs = qs.filter(asignatura=asig)
    if grado.isdigit():
        qs = qs.filter(grado=int(grado))
    if q:
        qs = qs.filter(texto__icontains=q)
    puede = es_gestion(request.user) and not es_solo_lectura(request.user)
    form = ObjetivoForm(request.POST or None, initial={"asignatura": asig or None, "grado": grado or None})
    if request.method == "POST":
        exigir(puede)
        if request.POST.get("eliminar"):
            oa = get_object_or_404(ObjetivoAprendizaje.objects.filter(establecimiento_id=Establecimiento.actual().pk),
                                   pk=request.POST["eliminar"])
            oa.delete()
            messages.success(request, "OA eliminado.")
            return redirect(request.get_full_path())
        if request.FILES.get("archivo"):
            from .importacion import importar_oas

            try:
                n = importar_oas(request.FILES["archivo"])
                messages.success(request, f"Se importaron {n} OA.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect(request.get_full_path())
        if form.is_valid():
            oa = form.save(commit=False)
            oa.establecimiento = Establecimiento.actual()
            if ObjetivoAprendizaje.objects.filter(establecimiento=oa.establecimiento, asignatura=oa.asignatura,
                                                  grado=oa.grado, numero=oa.numero).exists():
                form.add_error("numero", "Ya existe un OA propio con ese número para esa asignatura y nivel.")
            else:
                oa.save()
                messages.success(request, f"{oa.codigo} agregado.")
                return redirect(f"{request.path}?asignatura={oa.asignatura}&grado={oa.grado}")
    total = qs.count()
    return render(request, "academico/curriculum.html", {
        "oas": qs.order_by("asignatura", "grado", "numero")[:400], "total": total, "form": form, "puede": puede,
        "asignaturas": ObjetivoAprendizaje._meta.get_field("asignatura").choices, "grados": GRADOS_CURRICULUM,
        "asig": asig, "grado": grado, "q": q,
    })
