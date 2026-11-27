"""Gestión PME / SEP: acciones del Plan de Mejoramiento Educativo por dimensión, su avance y la rendición de
los gastos de la Subvención Escolar Preferencial. Lo ven Dirección, UTP e Inspectoría General."""
from collections import defaultdict

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import graficos
from .asistencia_personal import puede_registrar, puede_ver
from .forms import BootstrapMixin
from .models import DIMENSIONES_PME, AccionPME, GastoSEP, PlanMejoramiento, anio_actual
from .permisos import exigir


class PlanForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PlanMejoramiento
        fields = ["presupuesto_sep", "saldo_anterior", "objetivo_general"]
        widgets = {"objetivo_general": forms.Textarea(attrs={"rows": 2})}


class AccionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = AccionPME
        fields = ["dimension", "nombre", "descripcion", "responsable", "inicio", "termino", "monto_sep", "estado",
                  "avance", "medios_verificacion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3}),
                   "medios_verificacion": forms.Textarea(attrs={"rows": 2}),
                   "inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "termino": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean(self):
        d = super().clean()
        if d.get("estado") == AccionPME.Estado.EJECUTADA:
            d["avance"] = 100
        if d.get("inicio") and d.get("termino") and d["termino"] < d["inicio"]:
            self.add_error("termino", "El término no puede ser anterior al inicio.")
        return d


class GastoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = GastoSEP
        fields = ["fecha", "accion", "categoria", "detalle", "proveedor", "documento", "monto"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accion"].queryset = plan.acciones.all() if plan else AccionPME.objects.none()
        self.fields["accion"].empty_label = "Sin acción asociada"


def _plan(request, crear=False):
    try:
        anio = int(request.GET.get("anio") or anio_actual())
    except ValueError:
        anio = anio_actual()
    plan = PlanMejoramiento.objects.filter(anio=anio).first()
    if plan is None and crear:
        plan = PlanMejoramiento.objects.create(anio=anio)
    return plan, anio


@login_required
def pme(request):
    exigir(puede_ver(request.user))
    editable = puede_registrar(request.user)
    plan, anio = _plan(request, crear=editable)
    if request.method == "POST":
        exigir(editable)
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Presupuesto guardado.")
        return redirect(f"{request.path}?anio={anio}")
    contexto = {"plan": plan, "anio": anio, "editable": editable, "anios": sorted(
        set(PlanMejoramiento.objects.values_list("anio", flat=True)) | {anio_actual()}, reverse=True)}
    if plan is None:
        return render(request, "academico/pme.html", contexto)
    acciones = list(plan.acciones.all())
    gastado = defaultdict(int)
    gasto_dim = defaultdict(int)
    for g in plan.gastos.select_related("accion"):
        if g.accion_id:
            gastado[g.accion_id] += g.monto
            gasto_dim[g.accion.dimension] += g.monto
        else:
            gasto_dim["SIN"] += g.monto
    for a in acciones:
        a.ejecutado = gastado.get(a.pk, 0)
    dimensiones = []
    for clave, nombre in DIMENSIONES_PME:
        lista = [a for a in acciones if a.dimension == clave]
        dimensiones.append({"clave": clave, "nombre": nombre, "acciones": lista,
                            "avance": round(sum(a.avance for a in lista) / len(lista)) if lista else None,
                            "planificado": sum(a.monto_sep for a in lista), "ejecutado": gasto_dim.get(clave, 0)})
    total = plan.presupuesto_sep + plan.saldo_anterior
    ejecutado = sum(g for g in gasto_dim.values())
    planificado = sum(a.monto_sep for a in acciones)
    contexto.update({
        "form": PlanForm(instance=plan), "dimensiones": dimensiones, "n_acciones": len(acciones),
        "ejecutadas": sum(1 for a in acciones if a.estado == AccionPME.Estado.EJECUTADA),
        "atrasadas": [a for a in acciones if a.atrasada], "total": total, "planificado": planificado,
        "ejecutado": ejecutado, "saldo": total - ejecutado, "sin_accion": gasto_dim.get("SIN", 0),
        "pct_ejecucion": round(ejecutado * 100 / total) if total else None,
        "g_avance": graficos.barras([(d["nombre"], d["avance"]) for d in dimensiones], maximo=100, sufijo=" %", dec=0),
        "g_gasto": graficos.barras([(d["nombre"], d["ejecutado"] / 1_000_000) for d in dimensiones]
                                   + ([("Sin acción asociada", gasto_dim["SIN"] / 1_000_000)] if gasto_dim.get("SIN") else []),
                                   sufijo=" MM$", dec=1),
    })
    return render(request, "academico/pme.html", contexto)


@login_required
def accion_form(request, pk=None):
    exigir(puede_registrar(request.user))
    if pk:
        accion = get_object_or_404(AccionPME, pk=pk)
        plan = accion.plan
    else:
        plan, _ = _plan(request, crear=True)
        accion = AccionPME(plan=plan, dimension=request.GET.get("dimension") or "PEDAGOGICA")
    form = AccionForm(request.POST or None, instance=accion)
    if request.method == "POST":
        if request.POST.get("eliminar") and pk:
            accion.delete()
            messages.success(request, "Acción eliminada.")
            return redirect(f"/pme/?anio={plan.anio}")
        if form.is_valid():
            form.instance.avance = form.cleaned_data["avance"]
            form.save()
            messages.success(request, "Acción guardada.")
            return redirect(f"/pme/?anio={plan.anio}")
    return render(request, "academico/form.html", {
        "form": form, "titulo": f"{'Editar' if pk else 'Nueva'} acción del PME {plan.anio}",
        "ayuda": "Registre la acción con su dimensión, responsable, plazos y el monto SEP planificado. El avance y los "
                 "medios de verificación se actualizan durante el año; al marcarla «Ejecutada» queda en 100 %.",
        "volver": ("pme", None), "eliminar_red": bool(pk),
    })


@login_required
def gastos(request):
    exigir(puede_ver(request.user))
    editable = puede_registrar(request.user)
    plan, anio = _plan(request, crear=editable)
    form = GastoForm(request.POST or None, plan=plan) if editable and plan else None
    if request.method == "POST":
        exigir(editable)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.plan = plan
            gasto.save()
            messages.success(request, "Gasto registrado.")
            return redirect(f"{request.path}?anio={anio}")
    lista = list(plan.gastos.select_related("accion")) if plan else []
    if request.GET.get("exportar") == "excel" and plan:
        from io import BytesIO

        from openpyxl import Workbook

        from .views import XLSX, _descarga

        libro = Workbook()
        hoja = libro.active
        hoja.title = f"Gastos SEP {anio}"
        hoja.append(["Fecha", "Dimensión", "Acción PME", "Categoría", "Detalle", "Proveedor", "Documento", "Monto"])
        for g in lista:
            hoja.append([g.fecha, g.accion.get_dimension_display() if g.accion else "", str(g.accion or ""),
                         g.get_categoria_display(), g.detalle, g.proveedor, g.documento, g.monto])
        hoja.append(["", "", "", "", "", "", "TOTAL", sum(g.monto for g in lista)])
        for col, ancho in zip("ABCDEFGH", (11, 20, 34, 30, 40, 26, 18, 14)):
            hoja.column_dimensions[col].width = ancho
        for fila in hoja.iter_rows(min_row=2, min_col=8, max_col=8):
            for c in fila:
                c.number_format = '"$"#,##0'
        salida = BytesIO()
        libro.save(salida)
        return _descarga(salida.getvalue(), f"rendicion-sep-{anio}.xlsx", XLSX)
    por_categoria = defaultdict(int)
    for g in lista:
        por_categoria[g.get_categoria_display()] += g.monto
    return render(request, "academico/pme_gastos.html", {
        "plan": plan, "anio": anio, "gastos": lista, "form": form, "editable": editable,
        "total": sum(g.monto for g in lista),
        "g_categoria": graficos.barras(sorted(((k, v / 1_000_000) for k, v in por_categoria.items()),
                                              key=lambda x: -x[1]), sufijo=" MM$", dec=1),
    })


@login_required
@require_POST
def gasto_eliminar(request, pk):
    exigir(puede_registrar(request.user))
    gasto = get_object_or_404(GastoSEP, pk=pk)
    anio = gasto.plan.anio
    gasto.delete()
    messages.success(request, "Gasto eliminado.")
    return redirect(f"/pme/gastos/?anio={anio}")
