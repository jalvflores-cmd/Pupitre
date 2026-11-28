"""Vistas de Convivencia: biblioteca de protocolos y normativa tipo, y acceso rápido a entrevistas."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from . import convivencia_docs as docs
from .models import Anotacion, Establecimiento, Estudiante
from .permisos import estudiantes_visibles, exigir, gestiona_convivencia, ve_datos_sensibles

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@login_required
def documentos(request):
    return render(request, "academico/convivencia_documentos.html", {
        "protocolos": docs.PROTOCOLOS, "normativa": docs.NORMATIVA_TIPO, "formatos": docs.FORMATOS,
        "nota": docs.NOTA_REVISION,
    })


@login_required
def documento(request, clave):
    d = docs.TODOS.get(clave)
    if not d:
        raise Http404
    secciones = [(t, [(l.startswith("- "), l[2:] if l.startswith("- ") else l) for l in lineas])
                 for t, lineas in d.get("secciones", [])]
    return render(request, "academico/convivencia_documento.html", {
        "d": d, "secciones": secciones, "es_protocolo": d.get("tipo") == "protocolo", "normativa_base": docs.NORMATIVA_BASE,
        "principios": docs.PRINCIPIOS, "nota": docs.NOTA_REVISION,
        "formatos": docs.FORMATOS,
    })


@login_required
def documento_docx(request, clave):
    if clave not in docs.TODOS:
        raise Http404
    estudiante = None
    if (request.GET.get("estudiante") or "").isdigit():
        estudiante = get_object_or_404(Estudiante.objects.select_related("curso__nivel"), pk=request.GET["estudiante"])
        exigir(ve_datos_sensibles(request.user, estudiante))
    est = getattr(request, "establecimiento", None) or Establecimiento.actual()
    contenido = docs.generar_docx(clave, est, estudiante,
                                  responsable=request.user.get_full_name() if estudiante else "")
    nombre = clave + (f"_{slugify(estudiante.rut)}" if estudiante else "")
    respuesta = HttpResponse(contenido, content_type=DOCX)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}.docx"'
    return respuesta


@login_required
def entrevista_rapida(request):
    """Buscar un estudiante y registrar la entrevista, imprimir el formato o descargar el acta en un clic."""
    exigir(gestiona_convivencia(request.user))
    q = (request.GET.get("q") or "").strip()
    protocolo = (request.GET.get("protocolo") or "")[:30]
    resultados = []
    if len(q) >= 2:
        filtro = Q()
        for palabra in q.split():
            filtro &= (Q(nombres__icontains=palabra) | Q(apellido_paterno__icontains=palabra)
                       | Q(apellido_materno__icontains=palabra) | Q(rut__icontains=palabra.replace(".", "")))
        resultados = (estudiantes_visibles(request.user).filter(filtro, activo=True)
                      .select_related("curso__nivel").order_by("apellido_paterno", "nombres")[:25])
    pendientes = (Anotacion.objects.filter(estudiante__in=estudiantes_visibles(request.user), derivada=True)
                  .exclude(estado_derivacion="CERRADA").select_related("estudiante__curso__nivel")[:15])
    return render(request, "academico/convivencia_entrevista.html", {
        "q": q, "resultados": resultados, "protocolo": protocolo,
        "doc_protocolo": docs.POR_PROTOCOLO.get(protocolo), "pendientes": pendientes,
        "protocolos": docs.PROTOCOLOS,
    })
