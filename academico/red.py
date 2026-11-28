"""Panel del sostenedor: sus establecimientos, indicadores comparados y usuarios del sostenedor.

Lo usan el sostenedor(a) (solo lectura) y el administrador(a) de plataforma del sostenedor, que además crea
usuarios en cualquiera de sus establecimientos y entra a cada uno con permisos de administración.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import graficos
from .forms import BootstrapMixin
from .models import Curso, Establecimiento, Estudiante, Perfil, anio_actual
from .permisos import exigir
from .tenencia import en_establecimiento

ROLES_ESTABLECIMIENTO = [(r.value, r.label) for r in (
    Perfil.Rol.ADMIN, Perfil.Rol.DIRECTOR, Perfil.Rol.UTP, Perfil.Rol.INSPECTOR, Perfil.Rol.CONVIVENCIA,
    Perfil.Rol.PROFESOR)]
ROLES_SOSTENEDOR = [(r.value, r.label) for r in (Perfil.Rol.ADMIN_SOSTENEDOR, Perfil.Rol.SOSTENEDOR)]


def perfil_sostenedor(user):
    perfil = getattr(user, "perfil", None) if user.is_authenticated else None
    return perfil if perfil and perfil.de_sostenedor else None


class UsuarioRedForm(BootstrapMixin, forms.Form):
    destino = forms.ChoiceField(label="¿Dónde trabaja?")
    rol = forms.ChoiceField(label="Cargo", choices=[("Sostenedor", ROLES_SOSTENEDOR),
                                                     ("Establecimiento", ROLES_ESTABLECIMIENTO)])
    nombres = forms.CharField(max_length=150)
    apellidos = forms.CharField(max_length=150)
    usuario = forms.RegexField(label="Usuario", max_length=150, regex=r"^[a-zA-Z0-9._-]+$",
                               error_messages={"invalid": "Use solo letras sin tilde, números, punto, guion o guion bajo."})
    clave = forms.CharField(label="Contraseña inicial", min_length=8)

    def __init__(self, *args, sostenedor, **kwargs):
        super().__init__(*args, **kwargs)
        self.sostenedor = sostenedor
        self.fields["destino"].choices = [("", "Sostenedor (todos los establecimientos)")] + [
            (str(e.pk), e.nombre) for e in sostenedor.establecimientos.order_by("nombre")]
        self.fields["destino"].required = False

    def clean_usuario(self):
        u = self.cleaned_data["usuario"]
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe en la plataforma.")
        return u

    def clean(self):
        d = super().clean()
        de_sost = d.get("rol") in dict(ROLES_SOSTENEDOR)
        if d.get("rol") and de_sost != (not d.get("destino")):
            raise forms.ValidationError("Los cargos del sostenedor trabajan en todos los establecimientos; los demás "
                                        "cargos se asignan a un establecimiento.")
        return d


def indicadores(est, anio):
    """Indicadores del año de un establecimiento (se calculan dentro del establecimiento)."""
    from .alertas import baja_asistencia, bajo_rendimiento
    from .resultados import rendimiento_interno

    with en_establecimiento(est):
        por_curso, _, situaciones = rendimiento_interno(anio)
        cursos = list(Curso.objects.filter(anio=anio).select_related("nivel", "profesor_jefe"))
        n = sum(c["n"] for c in por_curso)
        def ponderado(clave):
            datos = [(c[clave], c["n"]) for c in por_curso if c[clave] is not None]
            total = sum(p for _, p in datos)
            return (sum(float(v) * p for v, p in datos) / total) if total else None
        return {
            "est": est, "n_estudiantes": Estudiante.objects.filter(activo=True).count(), "n_cursos": len(cursos),
            "promedio": ponderado("promedio"), "aprobacion": ponderado("aprobacion"),
            "asistencia": ponderado("asistencia"),
            "alertas_notas": len(bajo_rendimiento(cursos)), "alertas_asistencia": len(baja_asistencia(cursos)),
            "con_notas": n,
        }


@login_required
def red(request):
    perfil = perfil_sostenedor(request.user)
    exigir(perfil is not None)
    sost = perfil.sostenedor
    anio = anio_actual()
    admin = perfil.rol == Perfil.Rol.ADMIN_SOSTENEDOR
    form = UsuarioRedForm(request.POST or None, sostenedor=sost) if admin else None
    if request.method == "POST":
        exigir(admin)
        if form.is_valid():
            d = form.cleaned_data
            est = sost.establecimientos.filter(pk=d["destino"]).first() if d["destino"] else None
            with transaction.atomic():
                u = User.objects.create_user(d["usuario"], password=d["clave"], first_name=d["nombres"],
                                             last_name=d["apellidos"])
                Perfil.objects.create(usuario=u, rol=d["rol"], establecimiento=est,
                                      sostenedor=None if est else sost)
            messages.success(request, f"Usuario «{u.username}» creado{f' en {est}' if est else ''}.")
            return redirect("red")
    filas = [indicadores(e, anio) for e in sost.establecimientos.order_by("nombre")]
    corto = lambda f: f["est"].nombre
    return render(request, "academico/red.html", {
        "sostenedor": sost, "filas": filas, "anio": anio, "admin": admin, "form": form,
        "actual_id": request.session.get("establecimiento_id"),
        "usuarios": User.objects.filter(perfil__sostenedor=sost).select_related("perfil").order_by("first_name"),
        "g_promedio": graficos.barras([(corto(f), f["promedio"]) for f in filas if f["promedio"] is not None],
                                      maximo=7, umbral=4, umbral_txt="4,0", malo=lambda v: v < 4),
        "g_asistencia": graficos.barras([(corto(f), f["asistencia"]) for f in filas if f["asistencia"] is not None],
                                        maximo=100, sufijo=" %", malo=lambda v: v < 85),
    })


@login_required
@require_POST
def entrar(request, pk):
    perfil = perfil_sostenedor(request.user)
    exigir(perfil is not None)
    est = get_object_or_404(Establecimiento, pk=pk, sostenedor_id=perfil.sostenedor_id)
    request.session["establecimiento_id"] = est.pk
    messages.info(request, f"Está trabajando en {est}. Para volver al resumen use «Mis establecimientos» en el menú.")
    return redirect("inicio")


@login_required
@require_POST
def salir(request):
    exigir(perfil_sostenedor(request.user) is not None)
    request.session.pop("establecimiento_id", None)
    return redirect("red")


# --------------------------------------------------------------------------- planes territoriales (SLEP)

class InstrumentoForm(BootstrapMixin, forms.ModelForm):
    archivo = forms.FileField(label="Archivo (PDF, Word o Excel, opcional)", required=False,
                              help_text="Si los objetivos están vacíos, Pupitre propone las líneas que parecen objetivos.")

    class Meta:
        from .models import InstrumentoTerritorial
        model = InstrumentoTerritorial
        fields = ["tipo", "anio_inicio", "anio_fin", "objetivos", "observaciones"]
        widgets = {"objetivos": forms.Textarea(attrs={"rows": 6}), "observaciones": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["objetivos"].required = False

    def clean(self):
        d = super().clean()
        if d.get("anio_inicio") and d.get("anio_fin") and d["anio_fin"] < d["anio_inicio"]:
            self.add_error("anio_fin", "El término no puede ser anterior al inicio.")
        if not (d.get("objetivos") or "").strip() and not d.get("archivo"):
            self.add_error("objetivos", "Escriba los objetivos o suba el archivo del plan.")
        return d


def _objetivos_desde_texto(texto):
    import re
    lineas = []
    for l in (x.strip() for x in texto.splitlines()):
        if re.match(r"^(objetivo|oe\s*\d|l[ií]nea|eje|meta|\d+[.)-]\s+\S)", l, re.I) and 15 < len(l) < 300:
            lineas.append(re.sub(r"^(\d+[.)-]|oe\s*\d+[.:)-]?)\s*", "", l, flags=re.I))
    return "\n".join(dict.fromkeys(lineas))[:6000]


@login_required
def planes(request):
    from . import revision_pme as rv
    from .models import InstrumentoTerritorial, PlanMejoramiento, ProyectoEducativo

    perfil = perfil_sostenedor(request.user)
    exigir(perfil is not None)
    sost = perfil.sostenedor
    admin = perfil.rol == Perfil.Rol.ADMIN_SOSTENEDOR
    anio = anio_actual()
    editar = sost.instrumentos.filter(pk=request.GET.get("editar") or 0).first()
    form = InstrumentoForm(instance=editar) if admin else None
    if request.method == "POST":
        exigir(admin)
        if request.POST.get("slep") is not None:
            sost.es_slep = request.POST["slep"] == "1"
            sost.save(update_fields=["es_slep"])
            return redirect("red_planes")
        if request.POST.get("eliminar"):
            sost.instrumentos.filter(pk=request.POST["eliminar"]).delete()
            messages.success(request, "Plan eliminado.")
            return redirect("red_planes")
        form = InstrumentoForm(request.POST, request.FILES, instance=editar)
        if form.is_valid():
            inst = form.save(commit=False)
            inst.sostenedor = sost
            archivo = form.cleaned_data.get("archivo")
            if archivo:
                try:
                    texto = rv.extraer_texto(archivo.name, archivo.read())
                except ValueError as e:
                    form.add_error("archivo", str(e))
                    texto = None
                if texto is not None:
                    inst.archivo_nombre = archivo.name[:200]
                    if not inst.objetivos.strip():
                        inst.objetivos = _objetivos_desde_texto(texto)
            if not form.errors:
                if not inst.objetivos.strip():
                    form.add_error("objetivos", "No se encontraron objetivos en el archivo: escríbalos, uno por línea.")
                else:
                    inst.save()
                    messages.success(request, f"{inst.get_tipo_display()} guardado. Revise que los objetivos estén bien separados.")
                    return redirect("red_planes")
    filas = []
    for est in sost.establecimientos.filter(activo=True).order_by("nombre"):
        with en_establecimiento(est):
            plan = PlanMejoramiento.objects.filter(anio=anio).first()
            pei = ProyectoEducativo.objects.first()
            fila = {"est": est, "plan": plan, "pei": bool(pei and pei.completo), "n": 0, "t": None}
            if plan:
                elementos = rv.elementos_pme(plan, plan.documentos.first())
                fila["n"] = sum(1 for e in elementos if e["origen"].startswith("Acción"))
                fila["t"] = rv.alineamiento_territorial(sost, anio, elementos)
                fila["coherencia"] = rv.coherencia_pei(pei, elementos)["indice"] if pei else None
            filas.append(fila)
    return render(request, "academico/red_planes.html", {
        "sostenedor": sost, "admin": admin, "form": form, "editar": editar, "anio": anio, "filas": filas,
        "instrumentos": sost.instrumentos.all(), "enep": rv.ENEP[0], "mdc": rv.MDC[0], "nota": rv.NOTA_TERRITORIAL,
        "vigentes": InstrumentoTerritorial.vigentes(sost, anio),
    })
