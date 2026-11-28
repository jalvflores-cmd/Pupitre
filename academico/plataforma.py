"""Panel del superadministrador: establecimientos de la plataforma y sus módulos."""
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BootstrapMixin
from .models import MODULOS, MODULOS_DISPONIBLES, ROLES_CON_PERMISOS, Curso, Establecimiento, Estudiante, Perfil, Sostenedor
from .permisos import es_superadmin
from .tenencia import en_establecimiento


def solo_superadmin(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_superadmin(request.user):
            raise PermissionDenied("Solo el superadministrador de la plataforma.")
        return vista(request, *args, **kwargs)
    return login_required(envoltura)


class EstablecimientoForm(BootstrapMixin, forms.ModelForm):
    modulos = forms.MultipleChoiceField(
        label="Módulos activos", required=False, widget=forms.CheckboxSelectMultiple,
        choices=[(c, n) for c, n, _ in MODULOS_DISPONIBLES])

    class Meta:
        model = Establecimiento
        fields = ["nombre", "sostenedor", "rbd", "oferta", "comuna", "region", "director", "jefe_utp", "activo",
                  "modulos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modulos"].widget.attrs.pop("class", None)
        self.fields["sostenedor"].empty_label = "Sin sostenedor (establecimiento independiente)"
        roles = [(r, Perfil.Rol(r).label) for r in ROLES_CON_PERMISOS]
        actuales = self.instance.permisos_roles if self.instance.pk else {}
        for codigo, nombre, _ in MODULOS_DISPONIBLES:  # matriz de permisos: qué cargos usan cada módulo
            self.fields[f"perm_{codigo}"] = forms.MultipleChoiceField(
                label=nombre.split(" (")[0], required=False, choices=roles, widget=forms.CheckboxSelectMultiple,
                initial=(actuales or {}).get(codigo, ROLES_CON_PERMISOS))

    def matriz(self):
        return [self[f"perm_{c}"] for c, _, _ in MODULOS_DISPONIBLES]

    def save(self, commit=True):
        est = super().save(commit=False)
        est.permisos_roles = {c: self.cleaned_data[f"perm_{c}"] for c, _, _ in MODULOS_DISPONIBLES
                              if set(self.cleaned_data[f"perm_{c}"]) != set(ROLES_CON_PERMISOS)}
        if commit:
            est.save()
        return est


class NuevoAdministradorForm(BootstrapMixin, forms.Form):
    rol = forms.ChoiceField(label="Cargo", choices=[("ADMIN", "Administrador(a) de plataforma"),
                                                     ("DIRECTOR", "Director(a)"), ("UTP", "Jefe(a) de UTP")])
    nombres = forms.CharField(max_length=150)
    apellidos = forms.CharField(max_length=150)
    usuario = forms.RegexField(label="Usuario", max_length=150, regex=r"^[a-zA-Z0-9._-]+$",
                               error_messages={"invalid": "Use solo letras sin tilde, números, punto, guion o guion bajo."})
    clave = forms.CharField(label="Contraseña inicial", min_length=8)
    plan_oficial = forms.BooleanField(label="Crear asignaturas del plan oficial de Básica", required=False, initial=True)

    def clean_usuario(self):
        u = self.cleaned_data["usuario"]
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe en la plataforma.")
        return u


@solo_superadmin
def plataforma(request):
    lista = Establecimiento.objects.select_related("sostenedor").annotate(n_usuarios=Count("perfiles", distinct=True)).order_by("nombre")
    cursos = dict(Curso.todos.values_list("establecimiento").annotate(n=Count("id")))
    estudiantes = dict(Estudiante.todos.filter(activo=True).values_list("establecimiento").annotate(n=Count("id")))
    for e in lista:
        e.n_cursos, e.n_estudiantes = cursos.get(e.pk, 0), estudiantes.get(e.pk, 0)
        e.nombres_modulos = [n for c, n, _ in MODULOS if c in (e.modulos or [])]
    sostenedores = Sostenedor.objects.annotate(n_usuarios=Count("perfiles", distinct=True)).prefetch_related(
        "establecimientos")
    return render(request, "academico/plataforma.html", {
        "establecimientos": lista, "sostenedores": sostenedores, "proximos": [n for _, n, disp in MODULOS if not disp],
        "actual_id": request.session.get("establecimiento_id"),
    })


@solo_superadmin
def establecimiento_form(request, pk=None):
    est = get_object_or_404(Establecimiento, pk=pk) if pk else None
    form = EstablecimientoForm(request.POST or None, instance=est, initial=None if est else {
        "modulos": [c for c, _, _ in MODULOS_DISPONIBLES], "activo": True})
    admin_form = None if est else NuevoAdministradorForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and (admin_form is None or admin_form.is_valid()):
        with transaction.atomic():
            nuevo = form.save()
            if admin_form is not None:
                d = admin_form.cleaned_data
                with en_establecimiento(nuevo):
                    u = User.objects.create_user(d["usuario"], password=d["clave"], first_name=d["nombres"],
                                                 last_name=d["apellidos"])
                    Perfil.objects.create(usuario=u, rol=d["rol"], establecimiento=nuevo)
                    if d["plan_oficial"]:
                        from .plan_oficial import asegurar_catalogo
                        asegurar_catalogo()
        messages.success(request, f"Establecimiento «{nuevo}» guardado.")
        return redirect("plataforma")
    return render(request, "academico/plataforma_form.html", {"form": form, "admin_form": admin_form, "est": est})


@solo_superadmin
@require_POST
def entrar(request, pk):
    est = get_object_or_404(Establecimiento, pk=pk)
    request.session["establecimiento_id"] = est.pk
    messages.info(request, f"Está trabajando en {est}. Para volver al panel use «Plataforma» en el menú.")
    return redirect("inicio")


@solo_superadmin
@require_POST
def salir(request):
    request.session.pop("establecimiento_id", None)
    return redirect("plataforma")


class SostenedorForm(BootstrapMixin, forms.ModelForm):
    establecimientos = forms.ModelMultipleChoiceField(
        label="Establecimientos del sostenedor", required=False, widget=forms.CheckboxSelectMultiple,
        queryset=Establecimiento.objects.order_by("nombre"))

    modulos = forms.MultipleChoiceField(
        label="Módulos que pueden usar sus establecimientos", required=False, widget=forms.CheckboxSelectMultiple,
        choices=[(c, n) for c, n, _ in MODULOS_DISPONIBLES])

    class Meta:
        model = Sostenedor
        fields = ["nombre", "rut", "activo", "es_slep", "modulos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["establecimientos"].widget.attrs.pop("class", None)
        self.fields["modulos"].widget.attrs.pop("class", None)
        if not self.instance.pk:
            self.fields["modulos"].initial = [c for c, _, _ in MODULOS_DISPONIBLES]
        if self.instance.pk:
            self.fields["establecimientos"].initial = list(self.instance.establecimientos.all())


class AdminSostenedorForm(NuevoAdministradorForm):
    rol = forms.ChoiceField(label="Cargo", choices=[("ADMIN_SOSTENEDOR", "Administrador(a) de plataforma del sostenedor"),
                                                     ("SOSTENEDOR", "Sostenedor(a)")])
    plan_oficial = None


@solo_superadmin
def sostenedor_form(request, pk=None):
    sost = get_object_or_404(Sostenedor, pk=pk) if pk else None
    form = SostenedorForm(request.POST or None, instance=sost, initial=None if sost else {"activo": True})
    admin_form = None if sost else AdminSostenedorForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and (admin_form is None or admin_form.is_valid()):
        with transaction.atomic():
            nuevo = form.save()
            elegidos = form.cleaned_data["establecimientos"]
            nuevo.establecimientos.exclude(pk__in=[e.pk for e in elegidos]).update(sostenedor=None)
            Establecimiento.objects.filter(pk__in=[e.pk for e in elegidos]).update(sostenedor=nuevo)
            if admin_form is not None:
                d = admin_form.cleaned_data
                u = User.objects.create_user(d["usuario"], password=d["clave"], first_name=d["nombres"],
                                             last_name=d["apellidos"])
                Perfil.objects.create(usuario=u, rol=d["rol"], sostenedor=nuevo)
        messages.success(request, f"Sostenedor «{nuevo}» guardado.")
        return redirect("plataforma")
    return render(request, "academico/plataforma_form.html", {
        "form": form, "admin_form": admin_form, "est": sost, "es_sostenedor": True})
