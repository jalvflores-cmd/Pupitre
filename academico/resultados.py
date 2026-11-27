"""Resultados: rendimiento interno (gráficos), SIMCE y PAES."""
from collections import Counter, OrderedDict, defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from . import graficos
from .calculos import ASISTENCIA_MINIMA, promedio_simple, resumen_curso
from .forms import PaesForm, SimceForm
from .models import Curso, Establecimiento, ResultadoPaes, ResultadoSimce, anio_actual
from .permisos import es_gestion, es_solo_lectura, exigir, ve_todo

OFERTA_MEDIA = {"HC", "TP", "POLIVALENTE", "COMPLETO"}
OFERTA_BASICA = {"BASICA", "COMPLETO"}


def rendimiento_interno(anio):
    cursos = list(Curso.objects.filter(anio=anio).select_related("nivel").order_by("nivel__orden", "letra"))
    por_curso, por_asig, situaciones = [], defaultdict(list), Counter()
    for curso in cursos:
        _, _, resumenes = resumen_curso(curso)
        if not resumenes:
            continue
        proms = [r.promedio_general for r in resumenes if r.promedio_general is not None]
        con_sit = [r for r in resumenes if r.promedio_general is not None]
        aprob = (sum(1 for r in con_sit if r.situacion == "Promovido(a)") * 100 / len(con_sit)) if con_sit else None
        asist = [r.estudiante.porcentaje_asistencia for r in resumenes if r.estudiante.porcentaje_asistencia is not None]
        por_curso.append({"curso": curso, "promedio": promedio_simple(proms), "aprobacion": aprob,
                          "asistencia": (sum(asist) / len(asist)) if asist else None, "n": len(resumenes)})
        for r in resumenes:
            situaciones[r.situacion] += 1
            for f in r.asignaturas:
                if f.incide and f.final is not None:
                    por_asig[f.asignatura_curso.asignatura.nombre].append(f.final)
    asignaturas = sorted(
        [{"nombre": n, "promedio": promedio_simple(v), "rojos": sum(1 for x in v if x < Decimal("4")) * 100 / len(v)}
         for n, v in por_asig.items()], key=lambda a: a["promedio"] or 0)
    return por_curso, asignaturas, situaciones


@login_required
def resultados(request):
    exigir(ve_todo(request.user))
    est = Establecimiento.actual()
    puede = es_gestion(request.user) and not es_solo_lectura(request.user)
    pestana = request.GET.get("ver", "interno")
    simce_form = SimceForm(prefix="s")
    paes_form = PaesForm(prefix="p")
    if request.method == "POST":
        exigir(puede)
        if request.POST.get("eliminar_simce"):
            get_object_or_404(ResultadoSimce, pk=request.POST["eliminar_simce"]).delete()
            messages.success(request, "Resultado eliminado.")
            return redirect(request.get_full_path())
        if request.POST.get("eliminar_paes"):
            get_object_or_404(ResultadoPaes, pk=request.POST["eliminar_paes"]).delete()
            messages.success(request, "Resultado eliminado.")
            return redirect(request.get_full_path())
        form = SimceForm(request.POST, prefix="s") if "guardar_simce" in request.POST else PaesForm(request.POST, prefix="p")
        if form.is_valid():
            modelo = form._meta.model
            claves = {k: form.cleaned_data[k] for k in (("anio", "nivel", "prueba") if modelo is ResultadoSimce
                                                         else ("anio", "prueba"))}
            obj = modelo.objects.filter(**claves).first()
            if obj:  # mismo año, nivel y prueba: actualiza
                form = form.__class__(request.POST, prefix=form.prefix, instance=obj)
                form.is_valid()
            form.save()
            messages.success(request, "Resultado guardado.")
            return redirect(f"{request.path}?ver={'simce' if modelo is ResultadoSimce else 'paes'}")
        if isinstance(form, SimceForm):
            simce_form, pestana = form, "simce"
        else:
            paes_form, pestana = form, "paes"

    anio = anio_actual()
    contexto = {"pestana": pestana, "puede": puede, "simce_form": simce_form, "paes_form": paes_form, "anio": anio,
                "tiene_media": est.oferta in OFERTA_MEDIA or ResultadoPaes.objects.exists()}
    if pestana == "interno":
        por_curso, asignaturas, situaciones = rendimiento_interno(anio)
        contexto.update({
            "por_curso": por_curso, "asignaturas": asignaturas, "situaciones": situaciones.most_common(),
            "g_promedio": graficos.barras([(c["curso"].nombre_corto, c["promedio"]) for c in por_curso], maximo=7,
                                          umbral=4, umbral_txt="4,0", malo=lambda v: v < 4),
            "g_aprobacion": graficos.barras([(c["curso"].nombre_corto, c["aprobacion"]) for c in por_curso], maximo=100,
                                            sufijo=" %", dec=0, malo=lambda v: v < 85),
            "g_asistencia": graficos.barras([(c["curso"].nombre_corto, c["asistencia"]) for c in por_curso], maximo=100,
                                            sufijo=" %", umbral=ASISTENCIA_MINIMA, umbral_txt="85 %",
                                            malo=lambda v: v < ASISTENCIA_MINIMA),
            "g_asignaturas": graficos.barras([(a["nombre"], a["promedio"]) for a in asignaturas], maximo=7, umbral=4,
                                             umbral_txt="4,0", malo=lambda v: v < 4),
        })
    elif pestana == "simce":
        grupos = OrderedDict()
        for r in ResultadoSimce.objects.all().order_by("nivel", "prueba", "anio"):
            grupos.setdefault((r.get_nivel_display(), r.get_prueba_display()), []).append(r)
        tarjetas = []
        for (nivel, prueba), filas in grupos.items():
            anios = [r.anio for r in filas]
            series = [("Establecimiento", {r.anio: r.puntaje for r in filas}),
                      ("Nacional", {r.anio: r.puntaje_nacional for r in filas}),
                      ("Grupo socioeconómico similar", {r.anio: r.puntaje_gse for r in filas})]
            ultimo = filas[-1]
            previo = filas[-2] if len(filas) > 1 else None
            tarjetas.append({"nivel": nivel, "prueba": prueba, "filas": filas, "ultimo": ultimo,
                             "variacion": ultimo.puntaje - previo.puntaje if previo else None,
                             "vs_nacional": ultimo.puntaje - ultimo.puntaje_nacional if ultimo.puntaje_nacional else None,
                             "grafico": graficos.lineas(anios, series)})
        contexto["tarjetas"] = tarjetas
    elif pestana == "paes":
        grupos = OrderedDict()
        for r in ResultadoPaes.objects.all().order_by("prueba", "anio"):
            grupos.setdefault(r.get_prueba_display(), []).append(r)
        contexto["tarjetas"] = [{
            "prueba": p, "filas": filas, "ultimo": filas[-1],
            "variacion": filas[-1].puntaje - filas[-2].puntaje if len(filas) > 1 else None,
            "vs_nacional": filas[-1].puntaje - filas[-1].puntaje_nacional if filas[-1].puntaje_nacional else None,
            "grafico": graficos.lineas([r.anio for r in filas], [("Establecimiento", {r.anio: r.puntaje for r in filas}),
                                                                 ("Nacional", {r.anio: r.puntaje_nacional for r in filas})]),
        } for p, filas in grupos.items()]
    return render(request, "academico/resultados.html", contexto)
