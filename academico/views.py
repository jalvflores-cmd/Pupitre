from collections import defaultdict

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
    AnotacionForm, ArchivoExcelForm, EstudianteForm, EvaluacionForm, FuncionarioForm, SolicitudCambioForm, TallerForm,
)
from .models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Comentario, Curso, Establecimiento, Estudiante, Evaluacion,
    Funcionario, SolicitudCambio, anio_actual,
)
from .permisos import (
    asignaturas_curso_visibles, cursos_visibles, es_gestion, estudiantes_visibles, exigir, puede_editar_notas,
    es_solo_lectura, gestiona_convivencia, puede_anotar, puede_editar_contacto, puede_eliminar_anotacion,
    puede_solicitar_cambio, puede_ver_funcionarios, ve_todo, puede_ver_asignatura_curso, puede_ver_curso, puede_ver_estudiante, puede_ver_informe_curso, solo_gestion,
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
    return render(request, "academico/curso_detalle.html", {
        "curso": curso, "asignaturas": asignaturas, "resumenes": resumenes,
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
    estudiantes = list(ac.curso.estudiantes.filter(activo=True))

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
        "ac": ac, "evaluaciones": evaluaciones, "filas": filas, "editable": editable,
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
    if request.GET.get("exportar") == "excel":
        return _descarga(exportacion.excel_anotaciones(qs, str(curso or "Todos los cursos visibles")),
                         _nombre_archivo("anotaciones", curso, ext="xlsx"), XLSX)
    return render(request, "academico/convivencia.html", {
        "anotaciones": qs[:300], "total": qs.count(), "curso_id": curso_id, "tipo": tipo,
        "tipos": Anotacion.Tipo.choices,
        "cursos": cursos_visibles(request.user).filter(anio=anio_actual()).select_related("nivel"),
    })


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


# --------------------------------------------------------------------------- Talleres JEC

@login_required
def talleres(request):
    from django.contrib.auth.models import User

    form = None
    if es_gestion(request.user):
        form = TallerForm(
            request.POST or None,
            cursos=Curso.objects.filter(anio=anio_actual()).select_related("nivel"),
            profesores=User.objects.filter(is_active=True).order_by("first_name", "last_name"),
        )
        if request.method == "POST" and form.is_valid():
            datos = form.cleaned_data
            asignatura, _ = Asignatura.objects.get_or_create(
                nombre=datos["nombre"].strip(),
                defaults={"tipo": Asignatura.Tipo.TALLER, "incide_en_promedio": datos["incide_en_promedio"], "orden": 90})
            if asignatura.tipo != Asignatura.Tipo.TALLER:
                messages.error(request, f"«{asignatura}» ya existe como asignatura del plan de estudios. Use otro nombre.")
                return redirect("talleres")
            asignatura.incide_en_promedio = datos["incide_en_promedio"]
            asignatura.save(update_fields=["incide_en_promedio"])
            for curso in datos["cursos"]:
                AsignaturaCurso.objects.update_or_create(curso=curso, asignatura=asignatura, defaults={
                    "profesor": datos["profesor"], "horas_semanales": datos["horas_semanales"]})
            messages.success(request, f"Taller «{asignatura}» asignado a {len(datos['cursos'])} curso(s).")
            return redirect("talleres")
    elif request.method == "POST":
        exigir(False)
    lista = asignaturas_curso_visibles(request.user).filter(
        asignatura__tipo=Asignatura.Tipo.TALLER, curso__anio=anio_actual()).order_by(
        "asignatura__nombre", "curso__nivel__orden", "curso__letra")
    return render(request, "academico/talleres.html", {"talleres": lista, "form": form})


@login_required
@solo_gestion
@require_POST
def taller_quitar(request, pk):
    ac = get_object_or_404(AsignaturaCurso, pk=pk, asignatura__tipo=Asignatura.Tipo.TALLER)
    if ac.evaluaciones.exists():
        messages.error(request, "El taller ya tiene evaluaciones en este curso: elimínelas primero desde su libro de notas.")
    else:
        ac.delete()
        messages.success(request, "Taller quitado del curso.")
    return redirect("talleres")
