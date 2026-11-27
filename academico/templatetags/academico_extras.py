from django import template

from ..calculos import formato_nota
from ..models import NOTA_APROBACION
from ..rut import formatear_rut

register = template.Library()


@register.filter
def nota(valor):
    return formato_nota(valor)


@register.filter
def clase_nota(valor):
    """Clase CSS: rojo para notas insuficientes (bajo 4,0)."""
    if valor is None or valor == "":
        return ""
    return "nota-roja" if valor < NOTA_APROBACION else "nota-azul"


@register.filter
def obtener(diccionario, clave):
    if diccionario is None:
        return None
    return diccionario.get(clave)


@register.filter
def rut(valor):
    return formatear_rut(valor)


@register.filter
def horas(valor):
    """28.60 -> '28 h 36 min' (horas cronológicas)."""
    if valor is None:
        return "—"
    h, m = divmod(int(round(float(valor) * 60)), 60)
    return f"{h} h {m} min" if m else f"{h} h"


@register.filter
def pesos(valor):
    """1234567 -> $1.234.567"""
    try:
        return "$" + f"{int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


@register.filter
def nota_c(valor, conceptos=False):
    """Nota con formato chileno o, si el curso evalúa con conceptos, su concepto (MB, B, S, I)."""
    if conceptos and valor not in (None, ""):
        from academico.calculos import concepto
        return concepto(valor)
    return nota(valor)
