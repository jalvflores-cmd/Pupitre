from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from . import exportacion, importacion
from .calculos import resumen_curso
from .forms import (
    AnotacionForm, ArchivoExcelForm, EstudianteForm, EvaluacionForm, FuncionarioForm, SolicitudCambioForm,
    AgregarAsignaturaCursoForm, ConfiguracionEstablecimientoForm, DerivacionForm, PrimeraConfiguracionForm, EntrevistaForm, RedApoyoForm,
)
from .models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Comentario, Curso, Establecimiento, Estudiante, Evaluacion,
    Entrevista, Funcionario, RedApoyo, SolicitudCambio, anio_actual,
)
from .permisos import (
    asignaturas_curso_visibles, cursos_visibles, es_gestion, estudiantes_visibles, exigir, puede_editar_notas,
    es_solo_lectura, gestiona_convivencia, puede_anotar, puede_editar_contacto, puede_eliminar_anotacion,
    puede_solicitar_cambio, puede_ver_funcionarios, ve_todo, puede_ver_asignatura_curso, puede_ver_curso, puede_ver_estudiante, puede_ver_informe_curso, solo_gestion,
    puede_editar_entrevista, puede_registrar_entrevista, ve_datos_sensibles,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _descarga(contenido, nombre, tipo):
    respuesta = HttpResponse(contenido, content_type=tipo)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


def _nombre_archivo(*partes, ext):
    return "_".join(slugify(str(p)) for p in partes if p) + f".{ext}"


# --------------------------------------------------------------------------- Inicio y cursos

@login_required
def inicio(request):
    user = request.user
    contexto = {"mis_asignaturas": AsignaturaCurso.objects.filter(profesor=user, curso__anio=anio_actual())
                .select_related("curso__nivel", "asignatura").annotate(n_eval=Count("evaluaciones")),
                "mis_jefaturas": Curso.objects.filter(profesor_jefe=user, anio=anio_actual()).select_related("nivel")}
    if ve_todo(user):
        contexto.update({
            "n_cursos": Curso.objects.filter(anio=anio_actual()).count(),
            "n_estudiantes": Estudiante.objects.filter(activo=True).count(),
            "n_asignaturas": Asignatura.objects.count(),
            "ultimas_anotaciones": Anotacion.objects.select_related("estudiante__curso__nivel")[:8],
        })
    return render(request, "academico/inicio.html", contexto)


@login_required
def cursos(request):
    visibles = cursos_visibles(request.user)
    anios = sorted(set(visibles.values_list("anio", flat=True)), reverse=True) or [anio_actual()]
    try:
        anio = int(request.GET.get("anio") or anio_actual())
    except ValueError:
        anio = anio_actual()
    lista = (visibles.filter(anio=anio).select_related("nivel", "profesor_jefe")
             .annotate(n_est=Count("estudiantes", filter=Q(estudiantes__activo=True), distinct=True)))
    por_nivel = defaultdict(list)
    for c in lista:
        por_nivel[c.nivel].append(c)
    return render(request, "academico/cursos.html", {"por_nivel": dict(por_nivel), "anios": anios, "anio": anio})


@login_required
def curso_detalle(request, pk):
    curso = get_object_or_404(Curso.objects.select_related("nivel", "profesor_jefe"), pk=pk)
    exigir(puede_ver_curso(request.user, curso))
    asignaturas = [ac for ac in curso.asignaturas_curso.select_related("asignatura", "profesor")
                   if puede_ver_asignatura_curso(request.user, ac)]
    _, _, resumenes = resumen_curso(curso, asignaturas)
    gestion = es_gestion(request.user)
    del_plan = [ac for ac in asignaturas if ac.asignatura.tipo != Asignatura.Tipo.TALLER]
    talleres = [ac for ac in asignaturas if ac.asignatura.tipo == Asignatura.Tipo.TALLER]
    return render(request, "academico/curso_detalle.html", {
        "curso": curso, "asignaturas": asignaturas, "resumenes": resumenes,
        "del_plan": del_plan, "talleres": talleres,
        "grupos": [("Plan de estudios", del_plan), ("Talleres JEC (Jornada Escolar Completa)", talleres)],
        "horas_totales": sum((ac.horas_semanales or 0) for ac in asignaturas),
        "form_agregar": AgregarAsignaturaCursoForm(curso=curso, profesores=_profesores()) if gestion else None,
        "profesores": _profesores() if gestion else None,
        "informes": puede_ver_informe_curso(request.user, curso),
        "n_anotaciones": Anotacion.objects.filter(estudiante__curso=curso).count(),
    })


# --------------------------------------------------------------------------- Libro de notas

@login_required
def libro_notas(request, pk):
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor"), pk=pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    editable = puede_editar_notas(request.user, ac)
    evaluaciones = list(ac.evaluaciones.all())
    estudiantes = [e for e in ac.curso.estudiantes.filter(activo=True) if e.cursa(ac.asignatura)]
    sin_religion = (ac.curso.estudiantes.filter(activo=True, religion="").count()
                    if ac.asignatura.religion else 0)

    if request.method == "POST":
        exigir(editable)
        errores, cambios = [], 0
        existentes = {(c.estudiante_id, c.evaluacion_id): c
                      for c in Calificacion.objects.filter(evaluacion__in=evaluaciones)}
        with transaction.atomic():
            for est in estudiantes:
                for ev in evaluaciones:
                    campo = f"n_{est.id}_{ev.id}"
                    if campo not in request.POST:
                        continue
                    try:
                        nota = importacion.leer_nota(request.POST[campo].strip())
                    except ValueError as e:
                        errores.append(f"{est.nombre_completo} – {ev.nombre}: {e}")
                        continue
                    actual = existentes.get((est.id, ev.id))
                    if nota is None and actual:
                        actual.delete()
                        cambios += 1
                    elif nota is not None and (actual is None or actual.nota != nota):
                        Calificacion.objects.update_or_create(evaluacion=ev, estudiante=est, defaults={"nota": nota})
                        cambios += 1
            if errores:
                transaction.set_rollback(True)
        if errores:
            for e in errores[:15]:
                messages.error(request, e)
            messages.warning(request, "No se guardó ningún cambio. Corrija las notas marcadas e intente de nuevo.")
        else:
            messages.success(request, f"Notas guardadas ({cambios} cambios).")
            return redirect("libro_notas", pk=ac.pk)

    _, _, resumenes = resumen_curso(ac.curso, [ac], estudiantes)
    filas = [(r.estudiante, r.asignaturas[0]) for r in resumenes]
    return render(request, "academico/libro_notas.html", {
        "ac": ac, "evaluaciones": evaluaciones, "filas": filas, "editable": editable, "sin_religion": sin_religion,
        "evs_s1": [e for e in evaluaciones if e.semestre == 1], "evs_s2": [e for e in evaluaciones if e.semestre == 2],
    })


@login_required
def evaluacion_form(request, ac_pk=None, pk=None):
    if pk:
        evaluacion = get_object_or_404(Evaluacion, pk=pk)
        ac = evaluacion.asignatura_curso
    else:
        ac = get_object_or_404(AsignaturaCurso, pk=ac_pk)
        evaluacion = Evaluacion(asignatura_curso=ac)
    exigir(puede_editar_notas(request.user, ac))
    form = EvaluacionForm(request.POST or None, instance=evaluacion)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Evaluación guardada.")
        return redirect("libro_notas", pk=ac.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"{'Editar' if pk else 'Nueva'} evaluación – {ac}",
        "volver": ("libro_notas", ac.pk),
        "eliminar": ("evaluacion_eliminar", pk) if pk else None,
    })


@login_required
@require_POST
def evaluacion_eliminar(request, pk):
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    ac = evaluacion.asignatura_curso
    exigir(puede_editar_notas(request.user, ac))
    evaluacion.delete()
    messages.success(request, f"Evaluación «{evaluacion.nombre}» eliminada junto con sus notas.")
    return redirect("libro_notas", pk=ac.pk)


# --------------------------------------------------------------------------- Estudiantes

@login_required
def estudiantes(request):
    qs = estudiantes_visibles(request.user).select_related("curso__nivel").order_by(
        F("curso__anio").desc(nulls_last=True), F("curso__nivel__orden").asc(nulls_last=True), "curso__letra",
        "apellido_paterno", "apellido_materno", "nombres")
    q = request.GET.get("q", "").strip()
    curso_id = request.GET.get("curso", "")
    inactivos = request.GET.get("inactivos") == "1"
    if q:
        limpio = q.replace(".", "")
        qs = qs.filter(Q(rut__icontains=limpio) | Q(nombres__icontains=q) | Q(apellido_paterno__icontains=q)
                       | Q(apellido_materno__icontains=q))
    if curso_id.isdigit():
        qs = qs.filter(curso_id=curso_id)
    if not inactivos:
        qs = qs.filter(activo=True)
    if request.GET.get("exportar") == "excel":
        return _descarga(exportacion.excel_estudiantes(qs), "estudiantes.xlsx", XLSX)
    return render(request, "academico/estudiantes.html", {
        "estudiantes": qs[:1500], "total": qs.count(), "q": q, "curso_id": curso_id, "inactivos": inactivos,
        "cursos": cursos_visibles(request.user).filter(anio=anio_actual()).select_related("nivel"),
    })


@login_required
def estudiante_detalle(request, pk):
    est = get_object_or_404(Estudiante.objects.select_related("curso__nivel", "curso__profesor_jefe"), pk=pk)
    exigir(puede_ver_estudiante(request.user, est))
    resumen, informes = None, False
    if est.curso:
        acs = [ac for ac in est.curso.asignaturas_curso.select_related("asignatura", "profesor")
               if puede_ver_asignatura_curso(request.user, ac)]
        _, evaluaciones, resumenes = resumen_curso(est.curso, acs, [est])
        resumen = resumenes[0] if resumenes else None
        informes = puede_ver_informe_curso(request.user, est.curso)
    return render(request, "academico/estudiante_detalle.html", {
        "est": est, "resumen": resumen, "informes": informes,
        "anotaciones": est.anotaciones.select_related("asignatura", "autor"),
        "puede_solicitar": puede_solicitar_cambio(request.user, est),
        "solicitudes": (est.solicitudes.select_related("solicitante", "revisor")[:10]
                        if es_gestion(request.user) or puede_solicitar_cambio(request.user, est) else []),
        "puede_anotar": puede_anotar(request.user, est),
        "sensibles": ve_datos_sensibles(request.user, est),
        "redes": est.redes_apoyo.all() if ve_datos_sensibles(request.user, est) else [],
        "entrevistas": (est.entrevistas.select_related("entrevistador", "anotacion")
                        if ve_datos_sensibles(request.user, est) else []),
        "puede_entrevistar": puede_registrar_entrevista(request.user, est),
        "form_anotacion": AnotacionForm(asignaturas=_asignaturas_para_anotar(request.user, est)),
    })


@login_required
@solo_gestion
def estudiante_form(request, pk=None):
    est = get_object_or_404(Estudiante, pk=pk) if pk else Estudiante()
    form = EstudianteForm(request.POST or None, instance=est)
    form.fields["curso"].queryset = Curso.objects.select_related("nivel").filter(anio__gte=anio_actual() - 1)
    if request.method == "POST" and form.is_valid():
        est = form.save()
        messages.success(request, f"Estudiante {est} guardado.")
        return redirect("estudiante_detalle", pk=est.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": "Editar estudiante" if pk else "Nuevo estudiante",
        "volver": ("estudiante_detalle", pk) if pk else ("estudiantes", None),
    })


@login_required
def estudiante_contacto(request, pk):
    """Inspectoría y Convivencia actualizan directamente los datos de contacto."""
    from .forms import ContactoEstudianteForm

    est = get_object_or_404(Estudiante, pk=pk)
    exigir(puede_editar_contacto(request.user))
    form = ContactoEstudianteForm(request.POST or None, instance=est)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos de contacto actualizados.")
        return redirect("estudiante_detalle", pk=est.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"Datos de contacto – {est}",
        "ayuda": "Para cambiar nombre, RUT o fecha de nacimiento use «Solicitar modificación» (lo aprueba UTP).",
        "volver": ("estudiante_detalle", est.pk),
    })


# --------------------------------------------------------------------------- Solicitudes de modificación

@login_required
def solicitud_crear(request, est_pk):
    est = get_object_or_404(Estudiante.objects.select_related("curso"), pk=est_pk)
    exigir(puede_solicitar_cambio(request.user, est))
    form = SolicitudCambioForm(request.POST or None, instance=est)
    if request.method == "POST" and form.is_valid():
        cambios = form.cambios()
        if not cambios:
            messages.warning(request, "No modificó ningún dato, así que no se envió la solicitud.")
        else:
            SolicitudCambio.objects.create(estudiante=est, solicitante=request.user, cambios=cambios,
                                           motivo=form.cleaned_data["motivo"])
            messages.success(request, "Solicitud enviada. Los cambios se aplicarán cuando UTP la apruebe.")
            return redirect("estudiante_detalle", pk=est.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"Solicitar modificación de datos – {est}",
        "ayuda": "Corrija los datos que necesite cambiar e indique el motivo. Los cambios no se aplican "
                 "de inmediato: quedan pendientes hasta que Jefe(a) de UTP o Dirección los apruebe.",
        "boton": "Enviar solicitud", "volver": ("estudiante_detalle", est.pk),
    })


@login_required
def solicitudes(request):
    qs = SolicitudCambio.objects.select_related("estudiante__curso__nivel", "solicitante", "revisor")
    if not es_gestion(request.user):
        qs = qs.filter(solicitante=request.user)
    estado = request.GET.get("estado", SolicitudCambio.Estado.PENDIENTE)
    if estado in SolicitudCambio.Estado.values:
        qs = qs.filter(estado=estado)
    return render(request, "academico/solicitudes.html", {
        "solicitudes": qs[:200], "estado": estado, "estados": SolicitudCambio.Estado.choices,
    })


@login_required
@solo_gestion
@require_POST
def solicitud_resolver(request, pk):
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    solicitud = get_object_or_404(SolicitudCambio, pk=pk, estado=SolicitudCambio.Estado.PENDIENTE)
    accion = request.POST.get("accion")
    solicitud.comentario_revision = request.POST.get("comentario", "").strip()
    if accion == "aprobar":
        try:
            with transaction.atomic():
                solicitud.aplicar()
        except ValidationError as e:
            messages.error(request, "No se pudo aplicar la solicitud: " + " ".join(e.messages))
            return redirect("solicitudes")
        solicitud.estado = SolicitudCambio.Estado.APROBADA
    elif accion == "rechazar":
        solicitud.estado = SolicitudCambio.Estado.RECHAZADA
    else:
        return redirect("solicitudes")
    solicitud.revisor, solicitud.revisada = request.user, timezone.now()
    solicitud.save()
    messages.success(request, f"Solicitud {solicitud.get_estado_display().lower()}: {solicitud.estudiante}.")
    return redirect("solicitudes")


# --------------------------------------------------------------------------- Convivencia

def _asignaturas_para_anotar(user, est):
    if ve_todo(user) or not est.curso:
        return Asignatura.objects.all()
    return Asignatura.objects.filter(cursos__curso=est.curso, cursos__profesor=user)


@login_required
@require_POST
def anotacion_crear(request, est_pk):
    est = get_object_or_404(Estudiante, pk=est_pk)
    exigir(puede_anotar(request.user, est))
    form = AnotacionForm(request.POST, asignaturas=_asignaturas_para_anotar(request.user, est))
    if form.is_valid():
        anotacion = form.save(commit=False)
        anotacion.estudiante, anotacion.autor = est, request.user
        anotacion.save()
        messages.success(request, "Anotación registrada.")
    else:
        for campo, errs in form.errors.items():
            messages.error(request, f"{campo}: {', '.join(errs)}")
    return redirect("estudiante_detalle", pk=est.pk)


@login_required
@require_POST
def anotacion_eliminar(request, pk):
    anotacion = get_object_or_404(Anotacion, pk=pk)
    exigir(puede_eliminar_anotacion(request.user, anotacion))
    anotacion.delete()
    messages.success(request, "Anotación eliminada.")
    return redirect("estudiante_detalle", pk=anotacion.estudiante_id)


@login_required
def convivencia(request):
    qs = Anotacion.objects.filter(estudiante__in=estudiantes_visibles(request.user)).select_related(
        "estudiante__curso__nivel", "asignatura", "autor")
    curso_id, tipo = request.GET.get("curso", ""), request.GET.get("tipo", "")
    curso = None
    if curso_id.isdigit():
        curso = get_object_or_404(Curso, pk=curso_id)
        qs = qs.filter(estudiante__curso=curso)
    if tipo in Anotacion.Tipo.values:
        qs = qs.filter(tipo=tipo)
    derivadas = request.GET.get("derivadas", "")
    if derivadas == "1":
        qs = qs.filter(derivada=True)
    elif derivadas in ("PENDIENTE", "EN_PROCESO", "CERRADA"):
        qs = qs.filter(derivada=True, estado_derivacion=derivadas)
    elif derivadas == "PROTOCOLO":
        qs = qs.exclude(protocolo="")
    if request.GET.get("exportar") == "excel":
        return _descarga(exportacion.excel_anotaciones(qs, str(curso or "Todos los cursos visibles")),
                         _nombre_archivo("anotaciones", curso, ext="xlsx"), XLSX)
    return render(request, "academico/convivencia.html", {
        "anotaciones": qs[:300], "total": qs.count(), "curso_id": curso_id, "tipo": tipo,
        "tipos": Anotacion.Tipo.choices, "derivadas": derivadas,
        "cursos": cursos_visibles(request.user).filter(anio=anio_actual()).select_related("nivel"),
        "ve_protocolos": gestiona_convivencia(request.user),
        "pendientes": qs.model.objects.filter(estudiante__in=estudiantes_visibles(request.user), derivada=True,
                                              estado_derivacion="PENDIENTE").count(),
        "entrevistas": (Entrevista.objects.filter(estudiante__in=estudiantes_visibles(request.user))
                        .select_related("estudiante__curso__nivel", "entrevistador")[:10]
                        if gestiona_convivencia(request.user) else []),
        "redes_vigentes": (RedApoyo.objects.filter(vigente=True, estudiante__in=estudiantes_visibles(request.user))
                           .select_related("estudiante__curso__nivel")
                           if gestiona_convivencia(request.user) else []),
    })


# --------------------------------------------------------------------------- Convivencia: derivaciones, redes, entrevistas

@login_required
def anotacion_derivacion(request, pk):
    """Convivencia Escolar registra si se activó un protocolo y el seguimiento de la derivación."""
    anotacion = get_object_or_404(Anotacion.objects.select_related("estudiante__curso"), pk=pk)
    exigir(gestiona_convivencia(request.user) and not es_solo_lectura(request.user))
    form = DerivacionForm(request.POST or None, instance=anotacion)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Derivación actualizada.")
        return redirect("estudiante_detalle", pk=anotacion.estudiante_id)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"Derivación a Convivencia · {anotacion.estudiante}",
        "ayuda": f"Anotación del {anotacion.fecha:%d-%m-%Y} ({anotacion.get_tipo_display()}"
                 f"{' ' + anotacion.get_gravedad_display() if anotacion.gravedad else ''}): {anotacion.descripcion}",
        "volver": ("estudiante_detalle", anotacion.estudiante_id),
    })


@login_required
def red_apoyo_form(request, est_pk=None, pk=None):
    red = get_object_or_404(RedApoyo.objects.select_related("estudiante"), pk=pk) if pk else None
    est = red.estudiante if red else get_object_or_404(Estudiante, pk=est_pk)
    exigir(gestiona_convivencia(request.user) and not es_solo_lectura(request.user))
    form = RedApoyoForm(request.POST or None, instance=red)
    if request.method == "POST":
        if request.POST.get("eliminar") and red:
            red.delete()
            messages.success(request, "Red de apoyo eliminada.")
            return redirect("estudiante_detalle", pk=est.pk)
        if form.is_valid():
            red = form.save(commit=False)
            red.estudiante = est
            if not red.registrada_por_id:
                red.registrada_por = request.user
            red.save()
            messages.success(request, "Red de apoyo guardada.")
            return redirect("estudiante_detalle", pk=est.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"Red de apoyo externa · {est}",
        "ayuda": "Información sensible: solo la ven Dirección, UTP, Inspectoría, Convivencia y el profesor(a) jefe.",
        "volver": ("estudiante_detalle", est.pk),
        "eliminar_red": bool(red),
    })


@login_required
def entrevista_form(request, est_pk=None, pk=None):
    entrevista = get_object_or_404(Entrevista.objects.select_related("estudiante__curso"), pk=pk) if pk else None
    est = entrevista.estudiante if entrevista else get_object_or_404(Estudiante.objects.select_related("curso"), pk=est_pk)
    if entrevista:
        exigir(puede_editar_entrevista(request.user, entrevista) and not es_solo_lectura(request.user))
    else:
        exigir(puede_registrar_entrevista(request.user, est))
    inicial = {}
    if not entrevista:
        inicial = {"entrevistado": est.apoderado_nombre, "rut_entrevistado": est.apoderado_rut,
                   "parentesco": "Apoderado(a)" if est.apoderado_nombre else ""}
        if (request.GET.get("anotacion") or "").isdigit():
            a = est.anotaciones.filter(pk=request.GET["anotacion"]).first()
            if a:
                inicial.update({"anotacion": a, "protocolo": a.protocolo, "motivo": a.descripcion,
                                "tipo": Entrevista.Tipo.PROTOCOLO if a.protocolo else Entrevista.Tipo.APODERADO})
    form = EntrevistaForm(request.POST or None, instance=entrevista, initial=inicial, estudiante=est)
    if request.method == "POST" and form.is_valid():
        entrevista = form.save(commit=False)
        entrevista.estudiante = est
        if not entrevista.entrevistador_id:
            entrevista.entrevistador = request.user
        entrevista.save()
        messages.success(request, "Entrevista registrada. Puede descargarla en PDF para firmarla.")
        return redirect("estudiante_detalle", pk=est.pk)
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"{'Editar' if entrevista else 'Registrar'} entrevista · {est}",
        "ayuda": "Registro confidencial. Después de guardar, descargue el PDF para que los participantes lo firmen.",
        "volver": ("estudiante_detalle", est.pk),
    })


@login_required
def entrevista_pdf(request, pk):
    entrevista = get_object_or_404(Entrevista.objects.select_related("estudiante__curso__nivel", "entrevistador"), pk=pk)
    exigir(ve_datos_sensibles(request.user, entrevista.estudiante))
    return _descarga(exportacion.pdf_entrevista(entrevista.estudiante, entrevista),
                     _nombre_archivo("entrevista", entrevista.estudiante.rut, entrevista.fecha, ext="pdf"),
                     "application/pdf")


@login_required
def entrevista_formato_pdf(request, est_pk):
    """Formato de entrevista en blanco (con los datos del estudiante) para completar a mano."""
    est = get_object_or_404(Estudiante.objects.select_related("curso__nivel"), pk=est_pk)
    exigir(ve_datos_sensibles(request.user, est))
    return _descarga(exportacion.pdf_entrevista(est, None),
                     _nombre_archivo("formato_entrevista", est.rut, ext="pdf"), "application/pdf")


# --------------------------------------------------------------------------- Importación

@login_required
def importar(request):
    return render(request, "academico/importar.html", {
        "form": ArchivoExcelForm(),
        "puede_importar_estudiantes": es_gestion(request.user) or Curso.objects.filter(profesor_jefe=request.user).exists(),
        "asignaturas": [ac for ac in asignaturas_curso_visibles(request.user).filter(curso__anio=anio_actual())
                        if puede_editar_notas(request.user, ac)],
    })


def _procesar_importacion(request, funcion, *args):
    form = ArchivoExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        for errs in form.errors.values():
            messages.error(request, " ".join(errs))
        return None
    try:
        return funcion(form.cleaned_data["archivo"], *args)
    except importacion.ErrorImportacion as e:
        for err in e.errores[:25]:
            messages.error(request, err)
        if len(e.errores) > 25:
            messages.error(request, f"… y {len(e.errores) - 25} errores más.")
        messages.warning(request, "No se importó nada. Corrija el archivo y vuelva a intentarlo.")
    except Exception:  # archivo dañado o con formato inesperado
        messages.error(request, "No se pudo leer el archivo. Verifique que sea un Excel, CSV, Word o nómina SIGE válido.")
    return None


@login_required
@require_POST
def importar_estudiantes(request):
    """Dirección/UTP: cualquier archivo. Profesor(a) jefe: nómina SIGE de sus cursos."""
    if es_gestion(request.user):
        r = _procesar_importacion(request, importacion.importar_estudiantes)
    else:
        jefaturas = list(Curso.objects.filter(profesor_jefe=request.user))
        exigir(bool(jefaturas))
        r = _procesar_importacion(request, importacion.importar_estudiantes, jefaturas)
    if r:
        detalle = f"{r['creados']} estudiantes nuevos, {r['actualizados']} actualizados"
        if r.get("sige"):
            detalle = f"Nómina SIGE reconocida. {detalle}, {r['cursos']} cursos, {r['retirados']} marcados como retirados"
        messages.success(request, f"Importación lista: {detalle}.")
    return redirect("importar")


@login_required
@require_POST
def importar_notas(request, pk):
    ac = get_object_or_404(AsignaturaCurso, pk=pk)
    exigir(puede_editar_notas(request.user, ac))
    r = _procesar_importacion(request, importacion.importar_notas, ac)
    if r:
        messages.success(request, f"Se importaron {r['notas']} notas en {r['evaluaciones']} evaluaciones.")
        return redirect("libro_notas", pk=ac.pk)
    return redirect(request.POST.get("volver") or "importar")


@login_required
@require_POST
def importar_anotaciones(request):
    exigir(not es_solo_lectura(request.user))
    r = _procesar_importacion(request, importacion.importar_anotaciones,
                              estudiantes_visibles(request.user), request.user)
    if r:
        messages.success(request, f"Se registraron {r['creadas']} anotaciones.")
    return redirect("importar")


@login_required
def plantilla(request, tipo, pk=None):
    if tipo == "estudiantes":
        exigir(es_gestion(request.user))
        return _descarga(importacion.plantilla_estudiantes(), "plantilla_estudiantes.xlsx", XLSX)
    if tipo == "anotaciones":
        exigir(not es_solo_lectura(request.user))
        return _descarga(importacion.plantilla_anotaciones(), "plantilla_anotaciones.xlsx", XLSX)
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura"), pk=pk)
    exigir(puede_editar_notas(request.user, ac))
    return _descarga(importacion.plantilla_notas(ac),
                     _nombre_archivo("notas", ac.asignatura, ac.curso.nombre_corto, ext="xlsx"), XLSX)


# --------------------------------------------------------------------------- Informes

@login_required
def informes(request):
    visibles = cursos_visibles(request.user).filter(anio=anio_actual()).select_related("nivel")
    return render(request, "academico/informes.html", {
        "cursos_completos": [c for c in visibles if puede_ver_informe_curso(request.user, c)],
        "asignaturas": asignaturas_curso_visibles(request.user).filter(curso__anio=anio_actual()),
    })


@login_required
def informe_notas_asignatura(request, pk):
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor"), pk=pk)
    exigir(puede_ver_asignatura_curso(request.user, ac))
    return _descarga(exportacion.excel_notas_asignatura(ac),
                     _nombre_archivo("notas", ac.asignatura, ac.curso.nombre_corto, ac.curso.anio, ext="xlsx"), XLSX)


def _curso_y_estudiantes(request, pk):
    curso = get_object_or_404(Curso.objects.select_related("nivel", "profesor_jefe"), pk=pk)
    exigir(puede_ver_informe_curso(request.user, curso))
    estudiantes_qs = curso.estudiantes.filter(activo=True)
    est_id = request.GET.get("estudiante", "")
    if est_id.isdigit():
        estudiantes_qs = curso.estudiantes.filter(pk=est_id)
    return curso, list(estudiantes_qs), (estudiantes_qs[0] if est_id.isdigit() and estudiantes_qs else None)


@login_required
def informe_notas_pdf(request, pk):
    curso, ests, uno = _curso_y_estudiantes(request, pk)
    nombre = _nombre_archivo("informe_notas", uno.rut if uno else curso.nombre_corto, curso.anio, ext="pdf")
    return _descarga(exportacion.pdf_informe_notas(curso, ests), nombre, "application/pdf")


@login_required
def informe_final_pdf(request, pk):
    curso, ests, uno = _curso_y_estudiantes(request, pk)
    nombre = _nombre_archivo("informe_final", uno.rut if uno else curso.nombre_corto, curso.anio, ext="pdf")
    return _descarga(exportacion.pdf_informe_final(curso, ests), nombre, "application/pdf")


@login_required
def informe_final_excel(request, pk):
    curso, _, _ = _curso_y_estudiantes(request, pk)
    return _descarga(exportacion.excel_informe_final_curso(curso),
                     _nombre_archivo("informe_final", curso.nombre_corto, curso.anio, ext="xlsx"), XLSX)


@login_required
def acta_final_pdf(request, pk):
    curso, _, _ = _curso_y_estudiantes(request, pk)
    return _descarga(exportacion.pdf_acta_final_curso(curso),
                     _nombre_archivo("acta_final", curso.nombre_corto, curso.anio, ext="pdf"), "application/pdf")


# --------------------------------------------------------------------------- Comentarios

@login_required
@require_POST
def comentario_enviar(request):
    texto = request.POST.get("texto", "").strip()
    tipo = request.POST.get("tipo")
    pagina = request.POST.get("pagina", "")[:300]
    if not pagina.startswith("/") or pagina.startswith("//"):
        pagina = ""
    if texto:
        Comentario.objects.create(usuario=request.user, texto=texto[:5000], pagina=pagina,
                                  tipo=tipo if tipo in Comentario.Tipo.values else Comentario.Tipo.OTRO)
        messages.success(request, "¡Gracias! Su comentario fue enviado.")
    return redirect(pagina or "/")


@login_required
@solo_gestion
def comentarios(request):
    qs = Comentario.objects.select_related("usuario__perfil")
    if request.GET.get("exportar") == "excel":
        from openpyxl import Workbook
        from io import BytesIO
        libro = Workbook()
        hoja = libro.active
        hoja.append(["Fecha", "Usuario", "Rol", "Tipo", "Página", "Comentario"])
        for c in qs:
            perfil = getattr(c.usuario, "perfil", None)
            hoja.append([c.creado.astimezone().strftime("%d-%m-%Y %H:%M"),
                         c.usuario.get_full_name() if c.usuario else "", perfil.get_rol_display() if perfil else "",
                         c.get_tipo_display(), c.pagina, c.texto])
        salida = BytesIO()
        libro.save(salida)
        return _descarga(salida.getvalue(), "comentarios.xlsx", XLSX)
    return render(request, "academico/comentarios.html", {"comentarios": qs[:300]})


# --------------------------------------------------------------------------- Funcionarios

@login_required
def funcionarios(request):
    exigir(puede_ver_funcionarios(request.user))
    est = Establecimiento.actual()
    qs = Funcionario.objects.all()
    if request.GET.get("inactivos") != "1":
        qs = qs.filter(activo=True)
    filas = [(f, *f.distribucion(est)) for f in qs]
    if request.GET.get("exportar") == "excel":
        from io import BytesIO
        from openpyxl import Workbook
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Funcionarios"
        hoja.append(["RUT", "Nombre", "Cargo", "Título", "Mención", "Contrato", "Horas contrato",
                     "Proporción", "Horas lectivas", "Horas no lectivas", "Teléfono", "Email"])
        for f, pct, lec, nolec in filas:
            hoja.append([f.rut_formateado, f.nombre_completo, f.get_cargo_display(), f.titulo, f.mencion,
                         f.get_tipo_contrato_display(), float(f.horas_contrato),
                         f"{pct}/{100 - pct}" if pct else "", float(lec) if lec is not None else None,
                         float(nolec) if nolec is not None else None, f.telefono, f.email])
        for col, ancho in zip("ABCDEFGHIJKL", (14, 32, 24, 30, 22, 12, 10, 11, 10, 10, 16, 26)):
            hoja.column_dimensions[col].width = ancho
        salida = BytesIO()
        libro.save(salida)
        return _descarga(salida.getvalue(), "funcionarios.xlsx", XLSX)
    docentes = [x for x in filas if x[1] is not None]
    return render(request, "academico/funcionarios.html", {
        "filas": filas, "est": est,
        "total_horas": sum(f.horas_contrato for f, *_ in filas),
        "total_lectivas": sum(x[2] for x in docentes),
        "total_no_lectivas": sum(x[3] for x in docentes),
        "inactivos": request.GET.get("inactivos") == "1",
    })


@login_required
@solo_gestion
def funcionario_form(request, pk=None):
    from django.contrib.auth.models import User

    funcionario = get_object_or_404(Funcionario, pk=pk) if pk else Funcionario()
    form = FuncionarioForm(request.POST or None, instance=funcionario)
    form.fields["usuario"].queryset = User.objects.filter(is_active=True).order_by("first_name", "last_name")
    form.fields["usuario"].label_from_instance = lambda u: f"{u.get_full_name() or u.username} ({u.username})"
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ficha guardada.")
        return redirect("funcionarios")
    return render(request, "academico/form.html", {
        "form": form, "titulo": "Editar funcionario(a)" if pk else "Nuevo funcionario(a)",
        "ayuda": "La proporción lectiva/no lectiva se calcula sola: 65/35 en general, y 60/40 para docentes de "
                 "pre-kínder a 4° básico si el establecimiento está marcado con 80 % o más de alumnos prioritarios. "
                 "Puede fijarla a mano si corresponde otra.",
        "volver": ("funcionarios", None),
    })


@login_required
@solo_gestion
@require_POST
def prioritarios(request):
    est = Establecimiento.actual()
    est.alta_concentracion = request.POST.get("alta_concentracion") == "on"
    est.save()
    messages.success(request, "Proporción actualizada: " + (
        "docentes de pre-kínder a 4° básico con 60/40." if est.alta_concentracion else "todos los docentes con 65/35."))
    return redirect("funcionarios")


# --------------------------------------------------------------------------- Carga académica del curso
# (asignaturas del plan y talleres JEC se administran juntos, dentro de cada curso)

def _profesores():
    from django.contrib.auth.models import User
    return User.objects.filter(is_active=True).order_by("first_name", "last_name")


@login_required
@solo_gestion
@require_POST
def curso_asignatura_agregar(request, pk):
    curso = get_object_or_404(Curso.objects.select_related("nivel"), pk=pk)
    form = AgregarAsignaturaCursoForm(request.POST, curso=curso, profesores=_profesores())
    if not form.is_valid():
        for e in form.non_field_errors() + [e for f in form for e in f.errors]:
            messages.error(request, e)
        return redirect("curso_detalle", pk=curso.pk)
    datos = form.cleaned_data
    asignatura = datos["asignatura"]
    if not asignatura:
        asignatura = Asignatura.objects.filter(nombre__iexact=datos["nuevo_taller"]).first()
        if not asignatura:
            asignatura = Asignatura.objects.create(nombre=datos["nuevo_taller"], tipo=Asignatura.Tipo.TALLER,
                                                   incide_en_promedio=datos["incide_en_promedio"], orden=90)
    cursos = [curso]
    if datos["todo_el_nivel"]:
        cursos += list(Curso.objects.filter(nivel=curso.nivel, anio=curso.anio).exclude(pk=curso.pk))
    agregados = 0
    for c in cursos:
        _, creado = AsignaturaCurso.objects.get_or_create(curso=c, asignatura=asignatura, defaults={
            "profesor": datos["profesor"], "horas_semanales": datos["horas_semanales"]})
        agregados += creado
    messages.success(request, f"«{asignatura}» agregada a {agregados} curso(s).")
    return redirect("curso_detalle", pk=curso.pk)


@login_required
@solo_gestion
@require_POST
def curso_carga_guardar(request, pk):
    """Guarda profesor(a) y horas de cada asignatura o taller del curso."""
    from decimal import Decimal, InvalidOperation

    curso = get_object_or_404(Curso, pk=pk)
    profesores = {str(u.pk): u for u in _profesores()}
    cambios = 0
    for ac in curso.asignaturas_curso.all():
        prof = profesores.get(request.POST.get(f"profesor_{ac.pk}", ""))
        texto = (request.POST.get(f"horas_{ac.pk}") or "").replace(",", ".").strip()
        try:
            horas = Decimal(texto) if texto else None
        except InvalidOperation:
            messages.error(request, f"Horas no válidas en {ac.asignatura}.")
            continue
        if prof != ac.profesor or horas != ac.horas_semanales:
            ac.profesor, ac.horas_semanales = prof, horas
            ac.save(update_fields=["profesor", "horas_semanales"])
            cambios += 1
    messages.success(request, f"Carga académica guardada ({cambios} cambio(s)).")
    return redirect("curso_detalle", pk=curso.pk)


@login_required
@solo_gestion
@require_POST
def curso_asignatura_quitar(request, pk):
    ac = get_object_or_404(AsignaturaCurso.objects.select_related("asignatura"), pk=pk)
    if ac.evaluaciones.exists():
        messages.error(request, f"«{ac.asignatura}» ya tiene evaluaciones en este curso: elimínelas primero desde su libro de notas.")
    else:
        ac.delete()
        messages.success(request, f"«{ac.asignatura}» quitada del curso.")
    return redirect("curso_detalle", pk=ac.curso_id)


@login_required
@solo_gestion
@require_POST
def cargar_plan_oficial(request, pk=None):
    """Agrega el plan de estudios oficial de Enseñanza Básica a un curso o a todos los del año."""
    from .plan_oficial import aplicar_plan, asegurar_catalogo

    asignaturas = asegurar_catalogo()
    cursos = ([get_object_or_404(Curso.objects.select_related("nivel"), pk=pk)] if pk
              else Curso.objects.filter(anio=anio_actual()).select_related("nivel"))
    total, aplicados, sin_plan = 0, 0, []
    for curso in cursos:
        n = aplicar_plan(curso, asignaturas)
        if n is None:
            sin_plan.append(curso.nombre_corto)
        else:
            aplicados += 1
            total += n
    if aplicados:
        messages.success(request, f"Plan oficial cargado: {total} asignatura(s) agregada(s) en {aplicados} curso(s). "
                                  "Ahora asigne los profesores en cada curso.")
    if sin_plan:
        messages.warning(request, "Sin plan automático (solo 1° a 8° básico por ahora): " + ", ".join(sin_plan)
                         + ". Agregue sus asignaturas desde la página de cada curso.")
    return redirect("curso_detalle", pk=pk) if pk else redirect("cursos")


@login_required
def talleres(request):
    """Antigua sección separada de talleres: ahora los talleres se ven dentro de cada curso."""
    return redirect("cursos")


# --------------------------------------------------------------------------- Primera configuración (instalación nueva)

def bienvenida(request):
    from django.contrib.auth import login
    from django.contrib.auth.models import User

    from .models import Perfil
    from .primera_vez import plataforma_configurada

    if plataforma_configurada():
        return redirect("inicio")
    form = PrimeraConfiguracionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            est = Establecimiento.objects.first() or Establecimiento()
            for campo in ("nombre", "rbd", "comuna", "region", "director", "jefe_utp"):
                setattr(est, campo, d[campo].strip())
            if not est.director and d["rol"] == "DIRECTOR":
                est.director = f"{d['nombres']} {d['apellidos']}"
            if not est.jefe_utp and d["rol"] == "UTP":
                est.jefe_utp = f"{d['nombres']} {d['apellidos']}"
            est.save()
            u = User.objects.create_user(d["usuario"], password=d["clave1"], first_name=d["nombres"].strip(),
                                         last_name=d["apellidos"].strip(), is_superuser=True, is_staff=True)
            Perfil.objects.create(usuario=u, rol=d["rol"])
            if d["plan_oficial"]:
                from .plan_oficial import asegurar_catalogo
                asegurar_catalogo()
        login(request, u, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "¡Pupitre está listo! Siga los pasos de la guía: importe la nómina de SIGE, "
                                  "cargue el plan oficial en los cursos y cree las cuentas de los funcionarios.")
        return redirect("inicio")
    return render(request, "academico/bienvenida.html", {"form": form})


# --------------------------------------------------------------------------- Respaldos (instalación local)

@login_required
@solo_gestion
def respaldos_vista(request):
    from django import forms as dj_forms

    from . import respaldos

    if not respaldos.usa_sqlite():
        messages.info(request, "Los respaldos de esta versión en internet los hace el servicio de alojamiento.")
        return redirect("inicio")
    est = Establecimiento.objects.first()

    class ConfigForm(dj_forms.ModelForm):
        class Meta:
            model = Establecimiento
            fields = ["respaldo_carpeta_extra", "respaldo_conservar"]

    form = ConfigForm(request.POST if request.POST.get("accion") == "config" else None, instance=est)
    for f in form.fields.values():
        f.widget.attrs["class"] = "form-control"
    if request.method == "POST":
        if request.POST.get("accion") == "crear":
            try:
                r, advertencias = respaldos.crear("manual")
                messages.success(request, f"Respaldo creado: {r.nombre}")
                for a in advertencias:
                    messages.warning(request, a)
            except Exception as e:
                messages.error(request, f"No se pudo crear el respaldo: {e}")
            return redirect("respaldos")
        if request.POST.get("accion") == "config" and est and form.is_valid():
            form.save()
            messages.success(request, "Configuración de respaldos guardada.")
            return redirect("respaldos")
    return render(request, "academico/respaldos.html", {
        "lista": respaldos.listar(), "carpeta": settings.RESPALDOS_DIR, "form": form if est else None,
        "base": respaldos.ruta_base(),
    })


@login_required
@solo_gestion
def respaldo_descargar(request, nombre):
    from django.http import FileResponse, Http404

    from . import respaldos

    for r in respaldos.listar():
        if r.nombre == nombre:
            return FileResponse(open(r.ruta, "rb"), as_attachment=True, filename=r.nombre)
    raise Http404


# --------------------------------------------------------------------------- Configuración editable

def logo(request):
    est = Establecimiento.objects.first()
    if not est or not est.logo:
        from django.http import Http404
        raise Http404
    respuesta = HttpResponse(bytes(est.logo), content_type="image/png")
    respuesta["Cache-Control"] = "max-age=86400"
    return respuesta


@login_required
@solo_gestion
def configuracion(request):
    from django.forms import modelformset_factory

    from .models import OpcionCatalogo

    est = Establecimiento.objects.first() or Establecimiento(nombre="Establecimiento educacional")
    Listas = modelformset_factory(OpcionCatalogo, fields=["nombre", "activo"], extra=2)
    post = request.POST if request.method == "POST" else None
    seccion = request.POST.get("seccion") if post else None
    form = ConfiguracionEstablecimientoForm(post if seccion == "escuela" else None,
                                            request.FILES if seccion == "escuela" else None, instance=est)
    listas = {}
    for tipo, titulo in OpcionCatalogo.Tipo.choices:
        listas[tipo] = (titulo, Listas(post if seccion == tipo else None, prefix=tipo.lower(),
                                       queryset=OpcionCatalogo.objects.filter(tipo=tipo)))
    if seccion == "escuela" and form.is_valid():
        form.save()
        messages.success(request, "Datos del establecimiento guardados.")
        return redirect("configuracion")
    if seccion in listas:
        formset = listas[seccion][1]
        if formset.is_valid():
            n = OpcionCatalogo.objects.filter(tipo=seccion).count()
            for f in formset.forms:
                if not f.has_changed() or not f.cleaned_data.get("nombre"):
                    continue
                opcion = f.save(commit=False)
                if not opcion.pk:
                    opcion.tipo, opcion.orden = seccion, n
                    opcion.codigo = OpcionCatalogo.nuevo_codigo(seccion, opcion.nombre)
                    n += 1
                opcion.save()
            messages.success(request, "Lista actualizada.")
            return redirect("configuracion")
    for f in [form] + [fs for _, fs in listas.values()]:
        if getattr(f, "errors", None) and any(f.errors if isinstance(f.errors, list) else [f.errors]):
            messages.error(request, "Revise los datos marcados.")
            break
    for _, fs in listas.values():
        for f in fs.forms:
            f.fields["nombre"].widget.attrs["class"] = "form-control form-control-sm"
            f.fields["activo"].widget.attrs["class"] = "form-check-input"
    return render(request, "academico/configuracion.html", {"form": form, "listas": listas, "est": est})
