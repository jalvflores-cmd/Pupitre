"""Horarios de clases: jornada (bloques), generador automático y edición a mano.

El generador reparte las horas semanales de cada asignatura del curso (carga académica) en los bloques de la semana:
- un curso tiene una sola clase por bloque y un profesor(a) no puede estar en dos cursos a la vez;
- las horas se ubican de a dos bloques seguidos cuando se puede, y la misma asignatura se reparte en días distintos;
- lo puesto a mano queda «fijo» y el generador no lo mueve.
Prueba varias vueltas al azar y se queda con la que deja menos horas sin ubicar.
"""
import math
import random
from collections import defaultdict
from datetime import time

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BootstrapMixin
from .models import (DIAS_SEMANA, AsignaturaCurso, BloqueHorario, Curso, Establecimiento, HorarioClase,
                     anio_actual)
from .permisos import es_gestion, es_solo_lectura, exigir, usuarios_establecimiento, ve_todo

JORNADA_SUGERIDA = [  # bloques de 45 minutos (hora pedagógica)
    (time(8, 0), time(8, 45)), (time(8, 45), time(9, 30)), (time(9, 45), time(10, 30)), (time(10, 30), time(11, 15)),
    (time(11, 30), time(12, 15)), (time(12, 15), time(13, 0)), (time(13, 45), time(14, 30)),
    (time(14, 30), time(15, 15)), (time(15, 25), time(16, 10)),
]
VUELTAS = 25


def asegurar_jornada():
    if not BloqueHorario.objects.exists():
        for i, (ini, fin) in enumerate(JORNADA_SUGERIDA, start=1):
            BloqueHorario.objects.create(numero=i, inicio=ini, fin=fin)
    return list(BloqueHorario.objects.order_by("numero"))


def horas_de(ac):
    return int(math.ceil(float(ac.horas_semanales or 0)))


def generar(cursos, semilla=None):
    """Genera el horario de los cursos dados (borra lo no fijo de esos cursos). Devuelve {ac_id: horas sin ubicar}."""
    bloques = asegurar_jornada()
    por_dia = {d: [b for b in bloques if str(d) in b.dias] for d, _ in DIAS_SEMANA}
    cursos = list(cursos)
    ids = [c.pk for c in cursos]
    HorarioClase.objects.filter(curso_id__in=ids, fijo=False).delete()
    existentes = list(HorarioClase.objects.filter(curso__anio__in={c.anio for c in cursos})
                      .select_related("asignatura_curso"))
    cargas = list(AsignaturaCurso.objects.filter(curso_id__in=ids).select_related("asignatura"))
    ubicadas = defaultdict(int)
    for h in existentes:
        ubicadas[h.asignatura_curso_id] += 1

    # trozos a ubicar: de a 2 bloques seguidos y, si sobra, uno suelto
    trozos = []
    carga_profe = defaultdict(int)
    for ac in cargas:
        faltan = horas_de(ac) - ubicadas[ac.pk]
        carga_profe[ac.profesor_id] += max(faltan, 0)
        while faltan > 0:
            n = 2 if faltan >= 2 else 1
            trozos.append((ac, n))
            faltan -= n

    mejor = None
    rnd = random.Random(semilla)
    for _ in range(VUELTAS):
        curso_ocupado = {(h.curso_id, h.dia, h.bloque_id) for h in existentes}
        profe_ocupado = {(h.asignatura_curso.profesor_id, h.dia, h.bloque_id) for h in existentes
                         if h.asignatura_curso.profesor_id}
        dia_asig = defaultdict(int)
        horas_dia = defaultdict(int)
        for h in existentes:
            dia_asig[(h.asignatura_curso_id, h.dia)] += 1
            horas_dia[(h.curso_id, h.dia)] += 1
        orden = sorted(trozos, key=lambda t: (-carga_profe[t[0].profesor_id], -t[1], rnd.random()))
        nuevos, sin = [], defaultdict(int)

        def libre(ac, dia, grupo):
            return all((ac.curso_id, dia, b.pk) not in curso_ocupado and
                       (not ac.profesor_id or (ac.profesor_id, dia, b.pk) not in profe_ocupado) for b in grupo)

        def poner(ac, n):
            opciones = []
            for dia, lista in por_dia.items():
                for i in range(len(lista) - n + 1):
                    grupo = lista[i:i + n]
                    if n == 2 and grupo[1].numero != grupo[0].numero + 1:
                        continue
                    if libre(ac, dia, grupo):
                        costo = (dia_asig[(ac.pk, dia)] * 10 + horas_dia[(ac.curso_id, dia)]
                                 + grupo[0].numero * 0.6 + rnd.random())
                        opciones.append((costo, dia, grupo))
            if not opciones:
                return False
            _, dia, grupo = min(opciones, key=lambda o: o[0])
            for b in grupo:
                curso_ocupado.add((ac.curso_id, dia, b.pk))
                if ac.profesor_id:
                    profe_ocupado.add((ac.profesor_id, dia, b.pk))
                nuevos.append(HorarioClase(curso_id=ac.curso_id, asignatura_curso=ac, dia=dia, bloque=b))
            dia_asig[(ac.pk, dia)] += n
            horas_dia[(ac.curso_id, dia)] += n
            return True

        for ac, n in orden:
            if poner(ac, n):
                continue
            for _ in range(n):  # sin dos bloques seguidos: se intenta de a uno
                if not poner(ac, 1):
                    sin[ac.pk] += 1
        puntaje = sum(sin.values())
        if mejor is None or puntaje < mejor[0]:
            mejor = (puntaje, nuevos, dict(sin))
        if puntaje == 0:
            break
    with transaction.atomic():
        HorarioClase.objects.bulk_create(mejor[1])
    return mejor[2]


def pendientes(cursos):
    """Asignaturas con horas sin ubicar: [(ac, horas del plan, ubicadas)]."""
    puestas = defaultdict(int)
    for ac_id in HorarioClase.objects.filter(curso__in=cursos).values_list("asignatura_curso_id", flat=True):
        puestas[ac_id] += 1
    filas = []
    for ac in AsignaturaCurso.objects.filter(curso__in=cursos).select_related("curso__nivel", "asignatura", "profesor"):
        if puestas[ac.pk] < horas_de(ac):
            filas.append((ac, horas_de(ac), puestas[ac.pk]))
    return filas


def sobrecargados(cursos, bloques):
    """Profesores con más horas asignadas que bloques en la semana (imposible de ubicar todo)."""
    capacidad = sum(len(b.dias) for b in bloques)
    total = defaultdict(int)
    for ac in AsignaturaCurso.objects.filter(curso__in=cursos, profesor__isnull=False).select_related("profesor"):
        total[ac.profesor] += horas_de(ac)
    return [(p, h) for p, h in sorted(total.items(), key=lambda x: -x[1]) if h > capacidad], capacidad


def grilla(bloques, clases, clave):
    """Filas por bloque con una celda por día. clave(h) -> texto de la celda."""
    celdas = {(h.dia, h.bloque_id): h for h in clases}
    filas, anterior = [], None
    for b in bloques:
        recreo = anterior is not None and b.inicio > anterior.fin
        filas.append({"bloque": b, "recreo": recreo, "desde": anterior.fin if recreo else None,
                      "celdas": [{"dia": d, "h": celdas.get((d, b.pk)), "existe": str(d) in b.dias}
                                 for d, _ in DIAS_SEMANA]})
        anterior = b
    return filas


@login_required
def horarios(request):
    gestion = es_gestion(request.user) and not es_solo_lectura(request.user)
    anio = anio_actual()
    bloques = asegurar_jornada() if gestion else list(BloqueHorario.objects.order_by("numero"))
    cursos = list(Curso.objects.filter(anio=anio).select_related("nivel").order_by("nivel__orden", "letra"))
    todos = ve_todo(request.user)
    if not todos:
        mios = Curso.objects.filter(Q(asignaturas_curso__profesor=request.user) | Q(profesor_jefe=request.user))
        cursos = [c for c in cursos if c in set(mios)]
    profesores = list(usuarios_establecimiento().filter(asignaturas_curso__curso__anio=anio).distinct()) if todos \
        else [request.user]

    if request.method == "POST":
        exigir(gestion)
        accion = request.POST.get("accion")
        if accion == "generar":
            alcance = cursos if request.POST.get("curso") == "todos" else \
                [get_object_or_404(Curso, pk=request.POST.get("curso"))]
            sin = generar(alcance)
            faltan = sum(sin.values())
            if faltan:
                messages.warning(request, f"Horario generado para {len(alcance)} curso(s). Quedaron {faltan} hora(s) "
                                          "sin ubicar: revise el detalle bajo el horario.")
            else:
                messages.success(request, f"Horario generado para {len(alcance)} curso(s), con todas las horas ubicadas.")
        elif accion == "celda":
            curso = get_object_or_404(Curso, pk=request.POST.get("curso"))
            bloque = get_object_or_404(BloqueHorario, pk=request.POST.get("bloque"))
            dia = int(request.POST.get("dia"))
            HorarioClase.objects.filter(curso=curso, dia=dia, bloque=bloque).delete()
            if request.POST.get("ac"):
                ac = get_object_or_404(AsignaturaCurso, pk=request.POST["ac"], curso=curso)
                choque = HorarioClase.objects.filter(asignatura_curso__profesor=ac.profesor, dia=dia, bloque=bloque,
                                                     curso__anio=curso.anio).select_related("curso__nivel").first() \
                    if ac.profesor_id else None
                if choque:
                    messages.error(request, f"{ac.profesor.get_full_name()} ya tiene clase en {choque.curso.nombre_corto} "
                                            "a esa hora.")
                else:
                    HorarioClase.objects.create(curso=curso, asignatura_curso=ac, dia=dia, bloque=bloque, fijo=True)
        elif accion == "liberar":
            HorarioClase.objects.filter(curso_id=request.POST.get("curso"), fijo=True).update(fijo=False)
            messages.info(request, "Las clases puestas a mano ya no están fijas: el generador podrá moverlas.")
        elif accion == "vaciar":
            HorarioClase.objects.filter(curso_id=request.POST.get("curso")).delete()
        return redirect(f"{request.path}?{request.META.get('QUERY_STRING', '')}")

    # qué se muestra: un curso o un profesor(a)
    vista_profe = request.GET.get("profesor") or (not todos and not request.GET.get("curso"))
    contexto = {"gestion": gestion, "bloques": bloques, "cursos": cursos, "profesores": profesores,
                "dias": DIAS_SEMANA, "anio": anio}
    if vista_profe:
        profe = request.user if not todos else get_object_or_404(User, pk=request.GET.get("profesor"))
        exigir(todos or profe == request.user)
        clases = HorarioClase.objects.filter(asignatura_curso__profesor=profe, curso__anio=anio).select_related(
            "curso__nivel", "asignatura_curso__asignatura")
        contexto.update({"profe": profe, "filas": grilla(bloques, clases, None), "horas": clases.count()})
    else:
        curso = next((c for c in cursos if str(c.pk) == request.GET.get("curso")), cursos[0] if cursos else None)
        if curso is not None:
            clases = HorarioClase.objects.filter(curso=curso).select_related("asignatura_curso__asignatura",
                                                                            "asignatura_curso__profesor")
            cargas = list(AsignaturaCurso.objects.filter(curso=curso).select_related("asignatura", "profesor"))
            contexto.update({"curso": curso, "filas": grilla(bloques, clases, None), "cargas": cargas,
                             "horas": clases.count(), "horas_plan": sum(horas_de(a) for a in cargas)})
    if gestion and cursos:
        contexto["pendientes"] = pendientes(cursos)
        contexto["sobrecargados"], contexto["capacidad"] = sobrecargados(cursos, bloques)
        contexto["sin_horario"] = not HorarioClase.objects.filter(curso__in=cursos).exists()
    return render(request, "academico/horarios.html", contexto)


class BloqueForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = BloqueHorario
        fields = ["numero", "inicio", "fin", "dias"]
        widgets = {"inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}


@login_required
def jornada(request):
    exigir(es_gestion(request.user) and not es_solo_lectura(request.user))
    asegurar_jornada()
    Bloques = modelformset_factory(BloqueHorario, form=BloqueForm, extra=2, can_delete=True)
    formset = Bloques(request.POST or None, queryset=BloqueHorario.objects.order_by("numero"))
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Jornada guardada. Si cambió bloques, vuelva a generar los horarios.")
        return redirect("horarios")
    return render(request, "academico/jornada.html", {"formset": formset,
                                                      "establecimiento_nombre": Establecimiento.actual().nombre})


@login_required
def horarios_pdf(request):
    """Horario imprimible en hoja carta: un curso, un profesor(a), todos los cursos o todos los profesores."""
    from django.http import HttpResponse

    from .exportacion import pdf_horarios

    anio = anio_actual()
    todos = ve_todo(request.user)
    bloques = list(BloqueHorario.objects.order_by("numero"))
    cursos = list(Curso.objects.filter(anio=anio).select_related("nivel", "profesor_jefe").order_by("nivel__orden", "letra"))
    paginas = []
    relacionados = ("curso__nivel", "asignatura_curso__asignatura", "asignatura_curso__profesor")

    def pagina_curso(curso):
        clases = HorarioClase.objects.filter(curso=curso).select_related(*relacionados)
        jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
        paginas.append((f"Horario de clases {anio} · {curso.nombre_corto}",
                        f"Profesor(a) jefe: {jefe}" if jefe else "", grilla(bloques, clases, None), "curso"))

    def pagina_profe(profe):
        clases = HorarioClase.objects.filter(asignatura_curso__profesor=profe, curso__anio=anio).select_related(
            *relacionados)
        paginas.append((f"Horario de clases {anio} · {profe.get_full_name() or profe.username}",
                        f"{clases.count()} horas pedagógicas semanales", grilla(bloques, clases, None), "profesor"))

    if request.GET.get("todos") == "cursos":
        exigir(todos)
        for c in cursos:
            pagina_curso(c)
        nombre = f"horarios-cursos-{anio}.pdf"
    elif request.GET.get("todos") == "profesores":
        exigir(todos)
        for p in usuarios_establecimiento().filter(asignaturas_curso__curso__anio=anio).distinct():
            pagina_profe(p)
        nombre = f"horarios-profesores-{anio}.pdf"
    elif request.GET.get("profesor"):
        profe = get_object_or_404(User, pk=request.GET["profesor"])
        exigir(todos or profe == request.user)
        pagina_profe(profe)
        nombre = f"horario-{profe.username}-{anio}.pdf"
    else:
        curso = get_object_or_404(Curso, pk=request.GET.get("curso"))
        exigir(todos or Curso.objects.filter(Q(asignaturas_curso__profesor=request.user) |
                                             Q(profesor_jefe=request.user), pk=curso.pk).exists())
        pagina_curso(curso)
        nombre = f"horario-{curso.nombre_corto}-{anio}.pdf".replace(" ", "-").replace("°", "")
    respuesta = HttpResponse(pdf_horarios(paginas), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'inline; filename="{nombre}"'
    return respuesta
