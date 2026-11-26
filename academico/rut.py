"""Utilidades para el RUT chileno (Rol Único Tributario)."""
import re

from django.core.exceptions import ValidationError


def limpiar_rut(rut) -> str:
    """Quita puntos, guiones y espacios. Devuelve en mayúsculas: '123456785'."""
    if rut is None:
        return ""
    return re.sub(r"[^0-9kK]", "", str(rut)).upper()


def calcular_dv(cuerpo) -> str:
    """Calcula el dígito verificador con el algoritmo módulo 11."""
    suma, multiplicador = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def rut_es_valido(rut) -> bool:
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit() or not (1 <= len(cuerpo) <= 8):
        return False
    return calcular_dv(cuerpo) == dv


def normalizar_rut(rut) -> str:
    """Formato de almacenamiento: '12345678-5' (sin puntos)."""
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return limpio
    return f"{int(limpio[:-1])}-{limpio[-1]}"


def formatear_rut(rut) -> str:
    """Formato de presentación: '12.345.678-5'."""
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return str(rut or "")
    cuerpo = f"{int(limpio[:-1]):,}".replace(",", ".")
    return f"{cuerpo}-{limpio[-1]}"


def validar_rut(valor):
    """Validador para campos de modelo/formulario."""
    if valor and not rut_es_valido(valor):
        raise ValidationError("El RUT %(rut)s no es válido.", params={"rut": valor})
