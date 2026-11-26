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
