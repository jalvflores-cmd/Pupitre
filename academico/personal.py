"""Gestión de personal del sostenedor: tramos, evaluación docente y asignaciones (BRP, tramo y prioritarios).

Los montos son estimaciones mensuales a partir de los parámetros que ingresa el sostenedor (valores para 44 horas,
proporcionales a las horas de contrato). Reglas de la asignación por alta concentración de prioritarios (DFL 1 de
1996, art. 50, texto de la Ley 20.903):
- 60 % o más de prioritarios: 20 % de la asignación de tramo + un monto fijo.
- 80 % o más: además un monto fijo adicional para los tramos Avanzado, Experto I y Experto II.
- Rural con 45 % a menos de 60 %: 10 % de la asignación de tramo.
"""
from collections import Counter
from math import ceil
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from . import graficos
from .forms import BootstrapMixin
from .models import Establecimiento, Funcionario, ParametrosPersonal, Perfil, anio_actual
from .permisos import es_gestion, es_solo_lectura, exigir, puede_ver_funcionarios
from .tenencia import en_establecimiento

TRAMOS_ALTOS = {"AVANZADO", "EXPERTO_I", "EXPERTO_II"}
BIENIOS_MAX = 15


def _perfil(user):
    return getattr(user, "perfil", None) if user.is_authenticated else None


def alcance(request):
    """(establecimientos que ve, sostenedor o None, puede editar)."""
    perfil = _perfil(request.user)
    if perfil and perfil.de_sostenedor:
        ests = list(perfil.sostenedor.establecimientos.order_by("nombre"))
        return ests, perfil.sostenedor, perfil.rol == Perfil.Rol.ADMIN_SOSTENEDOR
    exigir(puede_ver_funcionarios(request.user))
    est = Establecimiento.actual()
    return [est], None, es_gestion(request.user) and not es_solo_lectura(request.user)


def parametros(sostenedor, establecimiento, anio, crear=False):
    filtro = {"sostenedor": sostenedor} if sostenedor else {"establecimiento": establecimiento,
                                                            "sostenedor__isnull": True}
    p = ParametrosPersonal.objects.filter(anio=anio, **filtro).first()
    if p is None:
        anterior = ParametrosPersonal.objects.filter(anio__lt=anio, **filtro).first()
        if crear:
            p = anterior or ParametrosPersonal(**{k: v for k, v in filtro.items() if "__" not in k})
            p.pk, p.anio = None, anio
        else:
            p = anterior or ParametrosPersonal(anio=anio)
    return p


def asignaciones(f, est, p):
    """Montos mensuales estimados {brp, tramo, prioritarios, total} de un funcionario."""
    cero = {"brp": 0, "tramo": 0, "prioritarios": 0, "total": 0}
    if f.cargo == Funcionario.Cargo.ASISTENTE:
        return cero
    factor = min(Decimal(f.horas_contrato or 0), Decimal(44)) / 44
    brp = ((p.brp_titulo if f.titulo else 0) + (p.brp_mencion if f.brp_mencion else 0)) * factor
    tramo = 0
    if f.tramo:
        bienios = min((f.anios_experiencia or 0) // 2, BIENIOS_MAX)
        tramo = (p.monto_tramo(f.tramo) + p.por_bienio * bienios) * factor
    prior = 0
    pct = est.pct_prioritarios
    if pct is not None and f.tramo:
        if pct >= 60:
            prior = Decimal("0.2") * tramo + p.prioritarios_fijo * factor
            if pct >= 80 and f.tramo in TRAMOS_ALTOS:
                prior += p.prioritarios_80 * factor
        elif est.rural and pct >= 45:
            prior = Decimal("0.1") * tramo
    montos = {"brp": round(brp), "tramo": round(tramo), "prioritarios": round(prior)}
    montos["total"] = sum(montos.values())
    return montos


class ParametrosForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ParametrosPersonal
        exclude = ["sostenedor", "establecimiento", "anio"]


class CarreraForm(BootstrapMixin, forms.ModelForm):
    """Ficha del funcionario(a) editable desde la gestión de personal (también por el sostenedor)."""

    class Meta:
        model = Funcionario
        fields = ["rut", "nombres", "apellido_paterno", "apellido_materno", "cargo", "titulo", "mencion",
                  "tipo_contrato", "horas_contrato", "primer_ciclo", "fecha_ingreso", "tramo", "anios_experiencia",
                  "brp_mencion", "evaluacion_docente", "evaluacion_anio", "telefono", "email", "activo"]
        widgets = {"fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_rut(self):
        from .rut import normalizar_rut
        rut = normalizar_rut(self.cleaned_data["rut"])
        if Funcionario.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un funcionario con este RUT en el establecimiento.")
        return rut


class NuevoFuncionarioForm(CarreraForm):
    establecimiento_destino = forms.ModelChoiceField(label="Establecimiento", queryset=Establecimiento.objects.none())

    def __init__(self, *args, establecimientos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["establecimiento_destino"].queryset = Establecimiento.objects.filter(
            pk__in=[e.pk for e in establecimientos])
        self.order_fields(["establecimiento_destino"] + list(self.Meta.fields))

    def clean_rut(self):  # se valida dentro del establecimiento elegido, al guardar
        from .rut import normalizar_rut
        return normalizar_rut(self.cleaned_data["rut"])


@login_required
def personal(request):
    ests, sost, editable = alcance(request)
    anio = int(request.GET.get("anio") or anio_actual())
    filtro_est = request.GET.get("est", "")
    p = parametros(sost, ests[0], anio)
    if request.method == "POST":
        exigir(editable)
        if "guardar_parametros" in request.POST:
            p = parametros(sost, ests[0], anio, crear=True)
            form = ParametrosForm(request.POST, instance=p)
            if form.is_valid():
                form.save()
                messages.success(request, f"Montos {anio} guardados.")
            else:
                messages.error(request, "Revise los montos: deben ser números enteros sin puntos.")
        elif "guardar_establecimientos" in request.POST:
            for e in ests:
                valor = request.POST.get(f"pct_{e.pk}", "").replace(",", ".").strip()
                try:
                    e.pct_prioritarios = Decimal(valor) if valor else None
                except ArithmeticError:
                    continue
                if e.pct_prioritarios is not None and not (0 <= e.pct_prioritarios <= 100):
                    continue
                e.rural = request.POST.get(f"rural_{e.pk}") == "on"
                e.save(update_fields=["pct_prioritarios", "rural"])
            messages.success(request, "Datos de los establecimientos guardados.")
        return redirect(f"{request.path}?anio={anio}&est={filtro_est}")

    filas = []
    for e in ests:
        if filtro_est and str(e.pk) != filtro_est:
            continue
        for f in Funcionario.todos.filter(establecimiento=e, activo=True):
            filas.append({"f": f, "est": e, **asignaciones(f, e, p)})
    docentes = [x for x in filas if x["f"].cargo != Funcionario.Cargo.ASISTENTE]
    tramos = Counter(x["f"].tramo for x in docentes)
    evals = Counter(x["f"].evaluacion_docente for x in docentes)
    total = {k: sum(x[k] for x in filas) for k in ("brp", "tramo", "prioritarios", "total")}

    if request.GET.get("exportar") == "excel":
        return _excel(filas, anio)
    return render(request, "academico/personal.html", {
        "ests": ests, "sostenedor": sost, "editable": editable, "anio": anio, "filtro_est": filtro_est,
        "filas": filas, "n_docentes": len(docentes), "total": total,
        "horas": sum(x["f"].horas_contrato for x in filas),
        "param_form": ParametrosForm(instance=p), "param_guardados": bool(p.pk and p.anio == anio),
        "param_anio": p.anio if p.pk else None,
        "por_mejorar": [x for x in docentes if x["f"].evaluacion_docente in ("BASICO", "INSATISFACTORIO")],
        "sin_tramo": [x for x in docentes if not x["f"].tramo],
        "g_tramos": graficos.barras([(n, tramos.get(c, 0)) for c, n in Funcionario.Tramo.choices]
                                    + [("Sin tramo", tramos.get("", 0))],
                                    maximo=max(tramos.values() or [1]), dec=0),
        "g_eval": graficos.barras([(n, evals.get(c, 0)) for c, n in Funcionario.Evaluacion.choices]
                                  + [("Sin evaluación", evals.get("", 0))],
                                  maximo=max(evals.values() or [1]), dec=0, rojas=("Básico", "Insatisfactorio")),
    })


def _excel(filas, anio):
    from io import BytesIO

    from openpyxl import Workbook

    from .views import XLSX, _descarga

    libro = Workbook()
    hoja = libro.active
    hoja.title = f"Personal {anio}"
    hoja.append(["Establecimiento", "RUT", "Nombre", "Cargo", "Horas", "Tramo", "Años exp.", "Evaluación docente",
                 "Año evaluación", "BRP", "Asig. tramo", "Asig. prioritarios", "Total asignaciones"])
    for x in filas:
        f = x["f"]
        hoja.append([x["est"].nombre, f.rut_formateado, f.nombre_completo, f.get_cargo_display(),
                     float(f.horas_contrato), f.get_tramo_display(), f.anios_experiencia,
                     f.get_evaluacion_docente_display(), f.evaluacion_anio, x["brp"], x["tramo"], x["prioritarios"],
                     x["total"]])
    for col, ancho in zip("ABCDEFGHIJKLM", (30, 14, 30, 24, 8, 12, 9, 18, 10, 12, 12, 14, 14)):
        hoja.column_dimensions[col].width = ancho
    salida = BytesIO()
    libro.save(salida)
    return _descarga(salida.getvalue(), f"personal-{anio}.xlsx", XLSX)


@login_required
def carrera(request, pk):
    ests, sost, editable = alcance(request)
    exigir(editable)
    f = get_object_or_404(Funcionario.todos, pk=pk, establecimiento__in=ests)
    with en_establecimiento(f.establecimiento):
        form = CarreraForm(request.POST or None, instance=f)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, f"Datos de {f} guardados.")
            return redirect("personal")
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"Ficha · {f}",
        "ayuda": f"{f.establecimiento}. El tramo y los años de experiencia determinan la asignación de tramo; el título "
                 "y la mención, la BRP. Las horas de contrato se usan en el análisis de dotación.",
        "volver": ("personal", None),
    })


@login_required
def nuevo(request):
    ests, sost, editable = alcance(request)
    exigir(editable)
    form = NuevoFuncionarioForm(request.POST or None, establecimientos=ests,
                                initial={"establecimiento_destino": request.GET.get("est") or ests[0].pk})
    if request.method == "POST" and form.is_valid():
        est = form.cleaned_data["establecimiento_destino"]
        with en_establecimiento(est):
            if Funcionario.objects.filter(rut=form.cleaned_data["rut"]).exists():
                form.add_error("rut", f"Ya existe un funcionario con este RUT en {est}.")
            else:
                f = form.save(commit=False)
                f.establecimiento = est
                f.save()
                messages.success(request, f"{f} agregado(a) a {est}.")
                return redirect("personal")
    return render(request, "academico/form.html", {
        "form": form, "titulo": "Nuevo funcionario(a)" + (f" · {sost}" if sost else ""),
        "ayuda": "El funcionario(a) queda en la dotación del establecimiento elegido y en la gestión de personal "
                 "del sostenedor.",
        "volver": ("personal", None),
    })


# --------------------------------------------------------------------------- dotación vs plan de estudios

HORAS_PEDAGOGICAS_POR_CRONOLOGICA = Decimal(60) / Decimal(45)  # hora pedagógica de 45 minutos
TOLERANCIA = Decimal("1")


def dotacion(est, anio):
    """Compara las horas del plan de estudios (carga académica de los cursos del año) con las horas lectivas de
    los docentes de aula del establecimiento (Ley 20.903: 65 % o 60 % del contrato, en horas pedagógicas)."""
    from collections import defaultdict

    from .models import AsignaturaCurso

    with en_establecimiento(est):
        acs = list(AsignaturaCurso.objects.filter(curso__anio=anio).select_related("profesor", "asignatura",
                                                                                   "curso__nivel"))
        horas_plan = sum(Decimal(ac.horas_semanales or 0) for ac in acs)
        por_profe = defaultdict(Decimal)
        sin_profesor = []
        for ac in acs:
            if ac.profesor_id:
                por_profe[ac.profesor_id] += Decimal(ac.horas_semanales or 0)
            elif ac.horas_semanales:
                sin_profesor.append(ac)
        filas, con_ficha = [], set()
        for f in Funcionario.objects.filter(activo=True).select_related("usuario"):
            asignadas = por_profe.get(f.usuario_id, Decimal(0)) if f.usuario_id else Decimal(0)
            if f.usuario_id:
                con_ficha.add(f.usuario_id)
            pct = f.porcentaje_lectivo(est)
            capacidad = (Decimal(f.horas_contrato) * pct / 100 * HORAS_PEDAGOGICAS_POR_CRONOLOGICA).quantize(
                Decimal("0.1")) if pct else None
            if capacidad is None and not asignadas:
                continue  # directivos, técnicos y asistentes sin horas de aula
            if capacidad is None:
                estado = "directivo"
            elif asignadas == 0:
                estado = "sin_carga"
            elif asignadas > capacidad + TOLERANCIA:
                estado = "sobrecarga"
            elif asignadas < capacidad - 2:
                estado = "holgura"
            else:
                estado = "ok"
            filas.append({"f": f, "capacidad": capacidad, "asignadas": asignadas, "estado": estado,
                          "diferencia": (capacidad - asignadas) if capacidad is not None else None})
        from django.contrib.auth import get_user_model
        sin_ficha = [(u, por_profe[u.pk]) for u in get_user_model().objects.filter(pk__in=set(por_profe) - con_ficha)]
    capacidad_total = sum(x["capacidad"] for x in filas if x["capacidad"] is not None)
    horas_directivos = sum(x["asignadas"] for x in filas if x["capacidad"] is None)
    horas_sin_profesor = sum(Decimal(ac.horas_semanales or 0) for ac in sin_profesor)
    balance = capacidad_total + horas_directivos - horas_plan
    horas_docente_44 = (Decimal(44) * Decimal("0.65") * HORAS_PEDAGOGICAS_POR_CRONOLOGICA).quantize(Decimal("0.1"))
    filas.sort(key=lambda x: ({"sobrecarga": 0, "sin_carga": 1, "holgura": 2, "ok": 3, "directivo": 4}[x["estado"]],
                              x["f"].apellido_paterno))
    return {
        "est": est, "filas": filas, "horas_plan": horas_plan, "capacidad": capacidad_total,
        "horas_directivos": horas_directivos, "horas_sin_profesor": horas_sin_profesor, "sin_profesor": sin_profesor,
        "sin_ficha": sin_ficha, "balance": balance, "docentes_equivalentes": (balance / horas_docente_44).quantize(
            Decimal("0.1")) if horas_docente_44 else None,
        "cobertura": ((capacidad_total + horas_directivos) * 100 / horas_plan) if horas_plan else None,
        "sobrecargados": sum(1 for x in filas if x["estado"] == "sobrecarga"),
        "sin_carga": sum(1 for x in filas if x["estado"] == "sin_carga"),
        "horas_docente_44": horas_docente_44, "disponibles": capacidad_total + horas_directivos,
    }


@login_required
def dotacion_vista(request):
    ests, sost, editable = alcance(request)
    anio = int(request.GET.get("anio") or anio_actual())
    resumen = [dotacion(e, anio) for e in ests]
    elegido = next((r for r in resumen if str(r["est"].pk) == request.GET.get("est")), resumen[0])
    return render(request, "academico/dotacion.html", {
        "resumen": resumen, "d": elegido, "anio": anio, "sostenedor": sost, "ests": ests,
        "g_cobertura": graficos.barras([(r["est"].nombre, r["cobertura"]) for r in resumen if r["cobertura"] is not None],
                                       maximo=50 * ceil(max([200] + [float(r["cobertura"]) for r in resumen if r["cobertura"]]) / 50),
                                       umbral=100, umbral_txt="100 %", sufijo=" %", dec=0,
                                       malo=lambda v: v < 100),
    })
