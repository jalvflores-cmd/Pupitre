"""Plan de estudios oficial de Enseñanza Básica (Decretos 2960/2012 y 628/2016), horas semanales con JEC."""
import re

from .models import Asignatura, AsignaturaCurso, Religion

PLAN = {
    "1-4": [("Lenguaje y Comunicación", 8), ("Inglés", 2), ("Matemática", 6),
            ("Historia, Geografía y Cs. Sociales", 3), ("Ciencias Naturales", 3), ("Artes Visuales", 2),
            ("Música", 2), ("Educación Física y Salud", 4), ("Tecnología", 1), ("Orientación", 0.5),
            ("Religión Católica", 2), ("Religión Evangélica", 2)],
    "5-6": [("Lenguaje y Comunicación", 6), ("Inglés", 3), ("Matemática", 6),
            ("Historia, Geografía y Cs. Sociales", 4), ("Ciencias Naturales", 4), ("Artes Visuales", 1.5),
            ("Música", 1.5), ("Educación Física y Salud", 2), ("Tecnología", 1), ("Orientación", 1),
            ("Religión Católica", 2), ("Religión Evangélica", 2)],
    "7-8": [("Lengua y Literatura", 6), ("Inglés", 3), ("Matemática", 6),
            ("Historia, Geografía y Cs. Sociales", 4), ("Ciencias Naturales", 4), ("Artes Visuales", 1.5),
            ("Música", 1.5), ("Educación Física y Salud", 2), ("Tecnología", 1), ("Orientación", 1),
            ("Religión Católica", 2), ("Religión Evangélica", 2)],
}
ORDEN = ["Lenguaje y Comunicación", "Lengua y Literatura", "Inglés", "Matemática",
         "Historia, Geografía y Cs. Sociales", "Ciencias Naturales", "Artes Visuales", "Música",
         "Educación Física y Salud", "Tecnología", "Orientación", "Religión Católica", "Religión Evangélica"]
CREDOS = {"Religión Católica": Religion.CATOLICA, "Religión Evangélica": Religion.EVANGELICA}


def asegurar_catalogo():
    """Crea las asignaturas oficiales que falten (no modifica las existentes). Devuelve {nombre: Asignatura}."""
    asignaturas = {}
    for i, nombre in enumerate(ORDEN):
        asignaturas[nombre], _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={
            "orden": i, "incide_en_promedio": nombre != "Orientación" and nombre not in CREDOS,
            "con_concepto": nombre == "Orientación", "religion": CREDOS.get(nombre, "")})
    return asignaturas


def grado_basica(curso):
    m = re.match(r"^\s*([1-8])\s*°?\s*(año\s+)?b[aá]sico", curso.nivel.nombre, re.IGNORECASE)
    return int(m.group(1)) if m else None


def aplicar_plan(curso, asignaturas=None):
    """Agrega al curso las asignaturas del plan oficial que le falten. Devuelve cuántas agregó (None si no aplica)."""
    grado = grado_basica(curso)
    if grado is None:
        return None
    asignaturas = asignaturas or asegurar_catalogo()
    plan = PLAN["1-4" if grado <= 4 else "5-6" if grado <= 6 else "7-8"]
    agregadas = 0
    for nombre, horas in plan:
        _, creada = AsignaturaCurso.objects.get_or_create(
            curso=curso, asignatura=asignaturas[nombre], defaults={"horas_semanales": horas})
        agregadas += creada
    return agregadas
