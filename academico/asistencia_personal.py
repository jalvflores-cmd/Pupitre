"""Asistencia del personal: registro diario y resumen mensual. Lo ven y registran Dirección, UTP e Inspectoría
General (y el administrador de plataforma); el sostenedor lo consulta."""
import calendar
import datetime
from collections import Counter, defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import AsistenciaFuncionario, Funcionario, Perfil
from .permisos import es_gestion, es_solo_lectura, exigir

E = AsistenciaFuncionario.Estado
PERMISOS_ADMINISTRATIVOS_ANIO = 6  # Estatuto Docente (art. 40): hasta 6 días hábiles al año
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def _perfil(user):
    return getattr(user, "perfil", None) if user.is_authenticated else None


def puede_ver(user):
    perfil = _perfil(user)
    return es_gestion(user) or bool(perfil and perfil.rol in (Perfil.Rol.INSPECTOR, Perfil.Rol.SOSTENEDOR))


def puede_registrar(user):
    perfil = _perfil(user)
    return (es_gestion(user) or bool(perfil and perfil.rol == Perfil.Rol.INSPECTOR)) and not es_solo_lectura(user)


def _fecha(texto, defecto):
    try:
        return datetime.date.fromisoformat(texto)
    except (TypeError, ValueError):
        return defecto


def _hora(texto):
    try:
        return datetime.time.fromisoformat(texto) if texto else None
    except ValueError:
        return None


@login_required
def diaria(request):
    exigir(puede_ver(request.user))
    editable = puede_registrar(request.user)
    hoy = timezone.localdate()
    fecha = _fecha(request.GET.get("fecha"), hoy)
    funcionarios = list(Funcionario.objects.filter(activo=True))
    registros = {a.funcionario_id: a for a in AsistenciaFuncionario.objects.filter(fecha=fecha)}
    if request.method == "POST":
        exigir(editable)
        with transaction.atomic():
            for f in funcionarios:
                estado = request.POST.get(f"estado_{f.pk}")
                if estado not in E.values:
                    continue
                try:
                    minutos = max(0, int(request.POST.get(f"atraso_{f.pk}") or 0))
                except ValueError:
                    minutos = 0
                AsistenciaFuncionario.objects.update_or_create(funcionario=f, fecha=fecha, defaults={
                    "estado": estado, "entrada": _hora(request.POST.get(f"entrada_{f.pk}")),
                    "salida": _hora(request.POST.get(f"salida_{f.pk}")),
                    "minutos_atraso": minutos if estado == E.ATRASO else 0,
                    "observacion": request.POST.get(f"obs_{f.pk}", "")[:200], "registrado_por": request.user})
        messages.success(request, f"Asistencia del {fecha:%d/%m/%Y} guardada.")
        return redirect(f"{request.path}?fecha={fecha.isoformat()}")
    filas = [(f, registros.get(f.pk)) for f in funcionarios]
    conteo = Counter(r.estado for r in registros.values())
    return render(request, "academico/asistencia_personal.html", {
        "fecha": fecha, "filas": filas, "editable": editable, "estados": E.choices, "registrado": bool(registros),
        "anterior": fecha - datetime.timedelta(days=1), "siguiente": fecha + datetime.timedelta(days=1), "hoy": hoy,
        "resumen": [(n, conteo.get(c, 0)) for c, n in E.choices if conteo.get(c)],
    })


def resumen_mes(anio, mes):
    """Por funcionario: conteo de cada estado, minutos de atraso, % de asistencia y permisos del año."""
    desde = datetime.date(anio, mes, 1)
    hasta = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])
    por_func = defaultdict(lambda: {"conteo": Counter(), "minutos": 0})
    for a in AsistenciaFuncionario.objects.filter(fecha__range=(desde, hasta)):
        d = por_func[a.funcionario_id]
        d["conteo"][a.estado] += 1
        d["minutos"] += a.minutos_atraso
    permisos_anio = Counter(AsistenciaFuncionario.objects.filter(fecha__year=anio, estado=E.PERMISO)
                            .values_list("funcionario_id", flat=True))
    filas = []
    for f in Funcionario.objects.filter(activo=True):
        d = por_func.get(f.pk, {"conteo": Counter(), "minutos": 0})
        c = d["conteo"]
        dias = sum(c.values())
        trabajados = c[E.PRESENTE] + c[E.ATRASO] + c[E.COMETIDO]
        filas.append({"f": f, "dias": dias, "trabajados": trabajados, "atrasos": c[E.ATRASO], "minutos": d["minutos"],
                      "inasistencias": c[E.AUSENTE], "licencias": c[E.LICENCIA], "permisos": c[E.PERMISO],
                      "otros": c[E.OTRO], "cometidos": c[E.COMETIDO], "permisos_anio": permisos_anio.get(f.pk, 0),
                      "pct": round(trabajados * 100 / dias, 1) if dias else None})
    return filas


@login_required
def mensual(request):
    exigir(puede_ver(request.user))
    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in request.GET.get("mes", "").split("-"))
        datetime.date(anio, mes, 1)
    except ValueError:
        anio, mes = hoy.year, hoy.month
    filas = resumen_mes(anio, mes)
    if request.GET.get("exportar") == "excel":
        from io import BytesIO

        from openpyxl import Workbook

        from .views import XLSX, _descarga

        libro = Workbook()
        hoja = libro.active
        hoja.title = f"{MESES[mes].capitalize()} {anio}"
        hoja.append(["RUT", "Nombre", "Cargo", "Días registrados", "Días trabajados", "% asistencia", "Atrasos",
                     "Minutos de atraso", "Inasistencias", "Licencias", "Permisos administrativos",
                     "Permisos adm. en el año", "Cometidos", "Otros permisos"])
        for x in filas:
            f = x["f"]
            hoja.append([f.rut_formateado, f.nombre_completo, f.get_cargo_display(), x["dias"], x["trabajados"], x["pct"],
                         x["atrasos"], x["minutos"], x["inasistencias"], x["licencias"], x["permisos"],
                         x["permisos_anio"], x["cometidos"], x["otros"]])
        for col, ancho in zip("ABCDEFGHIJKLMN", (14, 30, 24, 10, 10, 10, 9, 10, 10, 9, 12, 12, 10, 10)):
            hoja.column_dimensions[col].width = ancho
        salida = BytesIO()
        libro.save(salida)
        return _descarga(salida.getvalue(), f"asistencia-personal-{anio}-{mes:02d}.xlsx", XLSX)
    previo = datetime.date(anio, mes, 1) - datetime.timedelta(days=1)
    siguiente = datetime.date(anio, mes, 28) + datetime.timedelta(days=4)
    return render(request, "academico/asistencia_personal_mes.html", {
        "filas": filas, "anio": anio, "mes": mes, "mes_txt": f"{MESES[mes]} {anio}",
        "previo": f"{previo.year}-{previo.month:02d}", "siguiente": f"{siguiente.year}-{siguiente.month:02d}",
        "tope_permisos": PERMISOS_ADMINISTRATIVOS_ANIO,
        "totales": {k: sum(x[k] for x in filas) for k in ("atrasos", "minutos", "inasistencias", "licencias",
                                                            "permisos")},
    })
