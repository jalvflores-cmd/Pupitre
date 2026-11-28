"""Calendario del establecimiento: eventos de la comunidad (consejos, reuniones de apoderados, plazos, actividades),
recordatorios personales y, de forma automática, las evaluaciones del docente, los plazos del PME y los feriados
nacionales de fecha fija."""
import calendar
import datetime
from collections import defaultdict

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BootstrapMixin
from .models import AccionPME, EventoCalendario, Evaluacion, Perfil
from .permisos import es_gestion, es_solo_lectura, exigir, rol_de

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
# Feriados nacionales de fecha fija (los movibles se agregan como evento «Feriado o interferiado»).
FERIADOS_FIJOS = {(1, 1): "Año Nuevo", (5, 1): "Día del Trabajo", (5, 21): "Día de las Glorias Navales",
                  (7, 16): "Virgen del Carmen", (8, 15): "Asunción de la Virgen", (9, 18): "Independencia Nacional",
                  (9, 19): "Glorias del Ejército", (11, 1): "Todos los Santos", (12, 8): "Inmaculada Concepción",
                  (12, 25): "Navidad"}
ROLES_DESTINO = [(Perfil.Rol.DIRECTOR, "Dirección"), (Perfil.Rol.UTP, "UTP"), (Perfil.Rol.INSPECTOR, "Inspectoría"),
                 (Perfil.Rol.CONVIVENCIA, "Convivencia"), (Perfil.Rol.PROFESOR, "Profesores"),
                 (Perfil.Rol.SOSTENEDOR, "Sostenedor")]
COLORES = {"REUNION": "primary", "CONSEJO": "primary", "APODERADOS": "info", "PLAZO": "danger", "EVALUACION": "warning",
           "ACTIVIDAD": "success", "FERIADO": "secondary", "RECORDATORIO": "dark"}


def publica_eventos(user):
    """Dirección, UTP, administración, Inspectoría y Convivencia publican eventos para la comunidad."""
    perfil = getattr(user, "perfil", None)
    return es_gestion(user) or bool(perfil and perfil.rol in (Perfil.Rol.INSPECTOR, Perfil.Rol.CONVIVENCIA))


class EventoForm(BootstrapMixin, forms.ModelForm):
    roles = forms.MultipleChoiceField(label="Dirigido a", choices=ROLES_DESTINO, required=False,
                                      widget=forms.CheckboxSelectMultiple,
                                      help_text="Sin marcar = toda la comunidad.")

    class Meta:
        model = EventoCalendario
        fields = ["titulo", "tipo", "fecha", "hora", "descripcion", "roles", "privado"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "hora": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "descripcion": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, publica=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.publica = publica
        if not publica:  # solo recordatorios personales
            for campo in ("roles", "privado", "tipo"):
                del self.fields[campo]

    def save(self, commit=True):
        evento = super().save(commit=False)
        if not self.publica:
            evento.privado = True
            evento.tipo = EventoCalendario.Tipo.RECORDATORIO
        if evento.tipo == EventoCalendario.Tipo.RECORDATORIO:
            evento.privado = True
        if commit:
            evento.save()
        return evento


def eventos_visibles(user, desde, hasta):
    rol = rol_de(user)
    return [e for e in EventoCalendario.objects.filter(fecha__range=(desde, hasta)) if e.visible_para(user, rol)]


def items_del_periodo(user, desde, hasta):
    """Todo lo que el usuario ve en el calendario entre dos fechas, agrupado por día."""
    from .asistencia_personal import puede_ver

    dias = defaultdict(list)
    for e in eventos_visibles(user, desde, hasta):
        dias[e.fecha].append({"titulo": e.titulo, "hora": e.hora, "tipo": e.get_tipo_display(),
                              "color": COLORES.get(e.tipo, "primary"), "evento": e,
                              "detalle": e.descripcion})
    for ev in (Evaluacion.objects.filter(asignatura_curso__profesor=user, fecha__range=(desde, hasta))
               .select_related("asignatura_curso__asignatura", "asignatura_curso__curso__nivel")):
        ac = ev.asignatura_curso
        dias[ev.fecha].append({"titulo": f"{ev.nombre} · {ac.curso} {ac.asignatura.nombre}", "tipo": "Evaluación",
                               "color": "warning", "hora": None})
    if puede_ver(user):
        for a in AccionPME.objects.filter(termino__range=(desde, hasta)).exclude(estado=AccionPME.Estado.EJECUTADA):
            dias[a.termino].append({"titulo": f"Término acción PME: {a.nombre}", "tipo": "Plazo PME", "color": "danger",
                                    "hora": None})
    d = desde
    while d <= hasta:
        if (d.month, d.day) in FERIADOS_FIJOS:
            dias[d].insert(0, {"titulo": FERIADOS_FIJOS[(d.month, d.day)], "tipo": "Feriado nacional",
                               "color": "secondary", "hora": None})
        d += datetime.timedelta(days=1)
    for lista in dias.values():
        lista.sort(key=lambda x: (x["hora"] is not None, x["hora"] or datetime.time(0)))
    return dias


@login_required
def calendario_vista(request):
    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in request.GET.get("mes", "").split("-"))
        datetime.date(anio, mes, 1)
    except ValueError:
        anio, mes = hoy.year, hoy.month
    publica = publica_eventos(request.user)
    puede_crear = not es_solo_lectura(request.user)
    if request.method == "POST":
        exigir(puede_crear)
        form = EventoForm(request.POST, publica=publica)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.creado_por = request.user
            evento.save()
            messages.success(request, f"«{evento.titulo}» quedó en el calendario el {evento.fecha:%d/%m/%Y}.")
            return redirect(f"{request.path}?mes={evento.fecha:%Y-%m}")
    else:
        form = EventoForm(publica=publica, initial={"fecha": request.GET.get("fecha") or hoy})
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    items = items_del_periodo(request.user, semanas[0][0], semanas[-1][-1])
    grilla = [[{"fecha": d, "otro_mes": d.month != mes, "hoy": d == hoy, "items": items.get(d, [])} for d in semana]
              for semana in semanas]
    proximos = sorted(((d, x) for d, lista in items_del_periodo(request.user, hoy, hoy + datetime.timedelta(days=30)).items()
                       for x in lista), key=lambda p: (p[0], p[1]["hora"] or datetime.time(0)))
    anterior = datetime.date(anio, mes, 1) - datetime.timedelta(days=1)
    siguiente = datetime.date(anio, mes, 28) + datetime.timedelta(days=7)
    return render(request, "academico/calendario.html", {
        "grilla": grilla, "mes_txt": f"{MESES[mes]} {anio}", "form": form, "publica": publica,
        "puede_crear": puede_crear, "anterior": f"{anterior:%Y-%m}", "siguiente": f"{siguiente:%Y-%m}",
        "actual": f"{hoy:%Y-%m}", "proximos": proximos[:12],
        "dias_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    })


@login_required
@require_POST
def evento_eliminar(request, pk):
    evento = get_object_or_404(EventoCalendario, pk=pk)
    exigir(evento.creado_por_id == request.user.id or es_gestion(request.user))
    mes = f"{evento.fecha:%Y-%m}"
    evento.delete()
    messages.success(request, "Evento eliminado del calendario.")
    return redirect(f"/calendario/?mes={mes}")
