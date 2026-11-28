"""Vistas de la revisión del PME: PEI, archivo de Comunidad Escolar, coherencia, Marco para la Buena Dirección,
comentarios y revisión opcional con IA."""
import datetime
import re
from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import revision_pme as rv
from .asistencia_personal import puede_ver
from .asistente import ia_disponible
from .forms import BootstrapMixin
from .models import (DIMENSIONES_PME, AccionPME, ComentarioPME, DocumentoPME, Establecimiento, PlanMejoramiento,
                     ProyectoEducativo, anio_actual)
from .permisos import es_gestion, es_solo_lectura, exigir

MAX_ARCHIVO = 10 * 1024 * 1024
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def puede_editar(user):
    return es_gestion(user) and not es_solo_lectura(user)


def _pei():
    return ProyectoEducativo.objects.first()


def _plan(request, crear=False):
    try:
        anio = int(request.GET.get("anio") or request.POST.get("anio") or anio_actual())
    except ValueError:
        anio = anio_actual()
    plan = PlanMejoramiento.objects.filter(anio=anio).first()
    if plan is None and crear:
        plan = PlanMejoramiento.objects.create(anio=anio)
    return plan, anio


def _volver(anio, ancla=""):
    return redirect(f"/pme/revision/?anio={anio}{'#' + ancla if ancla else ''}")


class PeiForm(BootstrapMixin, forms.ModelForm):
    archivo = forms.FileField(label="Archivo del PEI (PDF o Word, opcional)", required=False,
                              help_text="Pupitre intenta ubicar la visión, la misión y los sellos. Revise lo que encuentre.")
    reemplazar = forms.BooleanField(label="Reemplazar lo que ya está escrito con lo que se lea del archivo",
                                    required=False)

    class Meta:
        model = ProyectoEducativo
        fields = ["vision", "mision", "sellos", "valores", "objetivos"]
        widgets = {k: forms.Textarea(attrs={"rows": r}) for k, r in
                   (("vision", 3), ("mision", 3), ("sellos", 5), ("valores", 3), ("objetivos", 4))}


class ComentarioForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ComentarioPME
        fields = ["tipo", "accion", "texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3, "placeholder": "Escriba su comentario o sugerencia"})}

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [c for c in ComentarioPME.Tipo.choices if c[0] != ComentarioPME.Tipo.IA]
        self.fields["accion"].queryset = plan.acciones.all() if plan else AccionPME.objects.none()
        self.fields["accion"].empty_label = "Comentario general del PME"


def _analisis(plan):
    pei = _pei()
    documento = plan.documentos.first()
    elementos = rv.elementos_pme(plan, documento)
    coherencia = rv.coherencia_pei(pei, elementos)
    mbdle = rv.cobertura_mbdle(elementos)
    calidad = rv.calidad_acciones(plan)
    return {"pei": pei, "documento": documento, "elementos": elementos, "coherencia": coherencia, "mbdle": mbdle,
            "mbdle_cubiertas": sum(d["cubiertas"] for d in mbdle), "mbdle_total": sum(d["total"] for d in mbdle),
            "calidad": calidad, "sugerencias": rv.sugerencias(pei, plan, coherencia, mbdle, calidad)}


@login_required
def revision(request):
    exigir(puede_ver(request.user))
    editar = puede_editar(request.user)
    plan, anio = _plan(request, crear=editar)
    if plan is None:
        return render(request, "academico/pme_revision.html", {"plan": None, "anio": anio})
    form = ComentarioForm(request.POST or None, plan=plan)
    if request.method == "POST":
        if form.is_valid():
            c = form.save(commit=False)
            c.plan, c.autor = plan, request.user
            c.save()
            messages.success(request, "Comentario agregado.")
            return _volver(anio, "comentarios")
    contexto = _analisis(plan)
    est = getattr(request, "establecimiento", None) or Establecimiento.actual()
    contexto.update({
        "plan": plan, "anio": anio, "editar": editar, "form": form, "nota_mbdle": rv.NOTA_MBDLE,
        "comentarios": plan.comentarios.select_related("autor", "accion"),
        "documentos": plan.documentos.defer("contenido", "texto"),
        "ia": ia_disponible(est) and editar, "dimensiones": dict(DIMENSIONES_PME),
        "anios": sorted(set(PlanMejoramiento.objects.values_list("anio", flat=True)) | {anio_actual()}, reverse=True),
    })
    return render(request, "academico/pme_revision.html", contexto)


@login_required
def pei_form(request):
    exigir(puede_ver(request.user))
    pei = _pei()
    anio = request.GET.get("anio", "")
    if request.method == "POST":
        exigir(puede_editar(request.user))
        form = PeiForm(request.POST, request.FILES, instance=pei)
        if form.is_valid():
            pei = form.save(commit=False)
            archivo = form.cleaned_data.get("archivo")
            if archivo:
                if archivo.size > MAX_ARCHIVO:
                    form.add_error("archivo", "El archivo supera los 10 MB.")
                    return render(request, "academico/form.html", _ctx_pei(form, anio))
                try:
                    texto = rv.extraer_texto(archivo.name, archivo.read())
                except ValueError as e:
                    form.add_error("archivo", str(e))
                    return render(request, "academico/form.html", _ctx_pei(form, anio))
                pei.archivo_nombre, pei.texto_archivo = archivo.name[:200], texto
                leido = rv.leer_pei(texto)
                for campo, valor in leido.items():
                    if form.cleaned_data.get("reemplazar") or not getattr(pei, campo).strip():
                        setattr(pei, campo, valor)
                encontrados = ", ".join({"vision": "visión", "mision": "misión", "sellos": "sellos",
                                         "valores": "valores"}[k] for k in leido) or "ninguna sección reconocible"
                messages.info(request, f"Del archivo se leyó: {encontrados}. Revise y corrija el texto si es necesario.")
            pei.save()
            messages.success(request, "PEI guardado.")
            return redirect(f"/pme/revision/pei/?anio={anio}") if archivo else _volver(anio or anio_actual(), "pei")
    else:
        form = PeiForm(instance=pei)
        if not puede_editar(request.user):
            for f in form.fields.values():
                f.disabled = True
    return render(request, "academico/form.html", _ctx_pei(form, anio))


def _ctx_pei(form, anio):
    return {"form": form, "titulo": "Proyecto Educativo Institucional (PEI)", "multipart": True,
            "ayuda": "Lo esencial del PEI para medir la coherencia del PME. Escriba un sello y un objetivo por línea.",
            "volver_url": f"/pme/revision/?anio={anio}"}


@login_required
@require_POST
def documento_subir(request):
    exigir(puede_editar(request.user))
    plan, anio = _plan(request, crear=True)
    archivo = request.FILES.get("archivo")
    if not archivo:
        messages.error(request, "Seleccione un archivo.")
        return _volver(anio, "archivo")
    if archivo.size > MAX_ARCHIVO:
        messages.error(request, "El archivo supera los 10 MB.")
        return _volver(anio, "archivo")
    contenido = archivo.read()
    try:
        texto = rv.extraer_texto(archivo.name, contenido)
    except ValueError as e:
        messages.error(request, str(e))
        return _volver(anio, "archivo")
    datos = rv.analizar_pme(texto)
    DocumentoPME.objects.create(plan=plan, nombre=archivo.name[:200], contenido=contenido, texto=texto, datos=datos,
                                subido_por=request.user)
    if not texto.strip():
        messages.warning(request, "El archivo se guardó, pero no tiene texto legible (¿es un PDF escaneado?).")
    else:
        messages.success(request, f"Archivo leído: {len(datos['objetivos'])} objetivo(s), {len(datos['metas'])} meta(s) y "
                                  f"{len(datos['acciones'])} acción(es) detectadas. Ya se consideran en la revisión.")
    return _volver(anio, "archivo")


def _fecha(texto):
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", texto or "")
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto or "")
    if m:
        try:
            return datetime.date(*map(int, m.groups()))
        except ValueError:
            return None
    return None


@login_required
@require_POST
def documento_importar(request, pk):
    exigir(puede_editar(request.user))
    doc = get_object_or_404(DocumentoPME, pk=pk)
    existentes = {rv.normalizar(a.nombre) for a in doc.plan.acciones.all()}
    n = 0
    for a in doc.datos.get("acciones", []):
        nombre = a.get("nombre", "").strip()[:200]
        if not nombre or rv.normalizar(nombre) in existentes:
            continue
        monto = int(re.sub(r"\D", "", a.get("monto", "")) or 0) if re.search(r"\d", a.get("monto", "")) else 0
        AccionPME.objects.create(
            plan=doc.plan, dimension=a.get("dimension") or "PEDAGOGICA", nombre=nombre,
            descripcion=a.get("descripcion", ""), responsable=a.get("responsable", "")[:120],
            inicio=_fecha(a.get("inicio")), termino=_fecha(a.get("termino")), monto_sep=min(monto, 10**12),
            medios_verificacion=a.get("medios", ""))
        existentes.add(rv.normalizar(nombre))
        n += 1
    messages.success(request, f"Se agregaron {n} acción(es) al PME {doc.plan.anio}." if n else
                     "No hay acciones nuevas para agregar: todas ya están en el PME.")
    return _volver(doc.plan.anio, "archivo")


@login_required
def documento_descargar(request, pk):
    exigir(puede_ver(request.user))
    doc = get_object_or_404(DocumentoPME, pk=pk)
    r = HttpResponse(bytes(doc.contenido), content_type="application/octet-stream")
    r["Content-Disposition"] = f'attachment; filename="{doc.nombre}"'
    return r


@login_required
@require_POST
def documento_eliminar(request, pk):
    exigir(puede_editar(request.user))
    doc = get_object_or_404(DocumentoPME, pk=pk)
    anio = doc.plan.anio
    doc.delete()
    messages.success(request, "Archivo eliminado.")
    return _volver(anio, "archivo")


@login_required
@require_POST
def comentario_accion(request, pk):
    c = get_object_or_404(ComentarioPME.objects.select_related("plan"), pk=pk)
    exigir(puede_editar(request.user) or c.autor_id == request.user.id)
    if request.POST.get("eliminar"):
        c.delete()
        messages.success(request, "Comentario eliminado.")
    else:
        c.resuelto = not c.resuelto
        c.save(update_fields=["resuelto"])
    return _volver(c.plan.anio, "comentarios")


@login_required
@require_POST
def revision_ia(request):
    est = getattr(request, "establecimiento", None) or Establecimiento.actual()
    exigir(puede_editar(request.user) and ia_disponible(est))
    plan, anio = _plan(request)
    exigir(plan is not None)
    a = _analisis(plan)
    texto, error = rv.revision_ia(a["pei"], plan, a["elementos"])
    if error:
        messages.error(request, error)
    else:
        ComentarioPME.objects.create(plan=plan, tipo=ComentarioPME.Tipo.IA, texto=texto, autor=request.user)
        messages.success(request, "La revisión con IA quedó guardada en los comentarios.")
    return _volver(anio, "comentarios")


@login_required
def informe_docx(request):
    """Informe de la revisión en Word, para compartir con el equipo directivo, el sostenedor o el Consejo Escolar."""
    from docx import Document
    from docx.shared import Pt

    exigir(puede_ver(request.user))
    plan, anio = _plan(request)
    exigir(plan is not None)
    a = _analisis(plan)
    est = getattr(request, "establecimiento", None) or Establecimiento.actual()
    doc = Document()
    doc.styles["Normal"].font.name, doc.styles["Normal"].font.size = "Calibri", Pt(11)
    doc.add_paragraph(f"{est.nombre}{'  ·  RBD ' + est.rbd if est.rbd else ''}").runs[0].bold = True
    doc.add_heading(f"Revisión del PME {anio}: coherencia con el PEI y el Marco para la Buena Dirección", level=0)
    c = a["coherencia"]
    doc.add_heading("Resumen", level=1)
    for t in (f"Índice de coherencia PEI–PME: {c['indice'] if c['indice'] is not None else 'sin datos'} %",
              f"Sellos del PEI presentes en el PME: {c['sellos_cubiertos']} de {c['sellos_total']}",
              f"Acciones vinculadas al PEI: {c['acciones_vinculadas']} de {c['acciones_total']}",
              "Marco para la Buena Dirección: " + "; ".join(f"{d['nombre']} {d['cubiertas']}/{d['total']}" for d in a["mbdle"])):
        doc.add_paragraph(t, style="List Bullet")
    doc.add_heading("Coherencia con el PEI", level=1)
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Sello / objetivo del PEI", "Acciones u objetivos del PME que lo abordan"
    for f in c["filas"]:
        fila = t.add_row().cells
        fila[0].text = f"{f['tipo']}: {f['texto']}"
        fila[1].text = "\n".join(e["titulo"] for e, _ in f["elementos"]) or "Sin acciones"
    doc.add_heading("Marco para la Buena Dirección y el Liderazgo Escolar", level=1)
    for d in a["mbdle"]:
        doc.add_paragraph(f"{d['nombre']} ({d['cubiertas']}/{d['total']} prácticas abordadas)").runs[0].bold = True
        for p in d["practicas"]:
            doc.add_paragraph(f"{'✓' if p['elementos'] else '○'} {p['texto']}"
                              + (f" — {len(p['elementos'])} elemento(s)" if p["elementos"] else ""), style="List Bullet")
    doc.add_heading("Sugerencias automáticas", level=1)
    for _, texto in a["sugerencias"]:
        doc.add_paragraph(texto, style="List Bullet")
    comentarios = plan.comentarios.select_related("autor", "accion")
    if comentarios:
        doc.add_heading("Comentarios y sugerencias del equipo", level=1)
        for co in comentarios:
            autor = co.autor.get_full_name() or co.autor.username if co.autor else ""
            p = doc.add_paragraph(f"{co.get_tipo_display()}{' · ' + co.accion.nombre if co.accion else ''} · {autor} · "
                                  f"{co.creado:%d-%m-%Y}{' · incorporado' if co.resuelto else ''}")
            p.runs[0].bold = True
            doc.add_paragraph(co.texto)
    doc.add_paragraph(rv.NOTA_MBDLE).runs[0].italic = True
    salida = BytesIO()
    doc.save(salida)
    r = HttpResponse(salida.getvalue(), content_type=DOCX)
    r["Content-Disposition"] = f'attachment; filename="revision_pme_{anio}.docx"'
    return r
