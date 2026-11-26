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
ORDEN_MEDIA = ORDEN + ["Educación Ciudadana", "Filosofía", "Ciencias para la Ciudadanía"]
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
        return aplicar_plan_media(curso)
    asignaturas = asignaturas or asegurar_catalogo()
    plan = PLAN["1-4" if grado <= 4 else "5-6" if grado <= 6 else "7-8"]
    agregadas = 0
    for nombre, horas in plan:
        _, creada = AsignaturaCurso.objects.get_or_create(
            curso=curso, asignatura=asignaturas[nombre], defaults={"horas_semanales": horas})
        agregadas += creada
    return agregadas


# --------------------------------------------------------------------------- Enseñanza Media
# 1° y 2° medio: Decreto Exento N° 1264 de 2016. 3° y 4° medio: formación general común (Decreto N° 193 de 2019)
# + plan diferenciado HC (electivos) o módulos de la especialidad TP. Horas semanales referenciales con JEC.

DECRETO_MEDIA_1_2 = "Decreto Exento N° 1264 de 2016"
DECRETO_MEDIA_3_4_HC = "Decreto Exento N° 876 de 2019"
DECRETO_MEDIA_3_4_TP = "Decreto Exento N° 954 de 2015"

PLAN_MEDIA = {
    "1-2": [("Lengua y Literatura", 6), ("Matemática", 7), ("Historia, Geografía y Cs. Sociales", 4),
            ("Ciencias Naturales", 6), ("Inglés", 4), ("Educación Física y Salud", 2), ("Tecnología", 2),
            ("Artes Visuales", 2), ("Orientación", 1), ("Religión Católica", 2), ("Religión Evangélica", 2)],
    "3-4": [("Lengua y Literatura", 3), ("Matemática", 3), ("Educación Ciudadana", 2), ("Filosofía", 2),
            ("Inglés", 2), ("Ciencias para la Ciudadanía", 2), ("Educación Física y Salud", 2), ("Orientación", 1),
            ("Religión Católica", 2), ("Religión Evangélica", 2)],
}

# Plan diferenciado Científico-Humanista: tres electivos de 6 horas (ejemplos de los programas del Mineduc)
ELECTIVOS_HC = {
    "Científico": ["Biología de los Ecosistemas", "Física", "Límites, Derivadas e Integrales"],
    "Humanista": ["Comprensión Histórica del Presente", "Taller de Literatura", "Lectura y Escritura Especializadas"],
    "Artístico": ["Interpretación Musical", "Diseño y Arquitectura", "Artes Visuales, Audiovisuales y Multimediales"],
}

# Módulos de especialidad Técnico-Profesional (Bases Curriculares TP). Horas semanales referenciales.
ESPECIALIDADES_TP = {
    "Administración": {
        3: [("Utilización de información contable", 6), ("Gestión comercial y tributaria", 6),
            ("Atención de clientes", 4), ("Organización de oficinas", 4), ("Aplicaciones informáticas para la gestión", 4)],
        4: [("Procesos administrativos", 6), ("Cálculo de remuneraciones y finiquitos", 6),
            ("Dotación de personal", 4), ("Desarrollo y bienestar del personal", 4), ("Emprendimiento y empleabilidad", 4)],
    },
    "Mecánica Automotriz": {
        3: [("Ajuste de motores", 6), ("Lectura de planos y manuales técnicos", 4), ("Mantenimiento de motores", 6),
            ("Mantenimiento de sistemas de dirección y suspensión", 4), ("Manejo de residuos automotrices", 4)],
        4: [("Mantenimiento de sistemas de transmisión y frenado", 6),
            ("Mantenimiento de sistemas eléctricos y electrónicos", 6),
            ("Mantenimiento de sistemas de seguridad y confortabilidad", 4),
            ("Mantenimiento de sistemas hidráulicos y neumáticos", 4), ("Emprendimiento y empleabilidad", 4)],
    },
    "Gastronomía": {
        3: [("Higiene para la elaboración de alimentos", 4), ("Elaboración de alimentos de baja complejidad", 6),
            ("Recepción y almacenamiento de insumos", 4), ("Preparación de bebidas", 4), ("Cocina chilena", 6)],
        4: [("Elaboración de menús y cartas", 4), ("Cocina internacional", 6), ("Panadería y pastelería", 6),
            ("Servicio de comedor", 4), ("Emprendimiento y empleabilidad", 4)],
    },
    "Electricidad": {
        3: [("Instalaciones eléctricas domiciliarias", 6), ("Lectura de planos eléctricos", 4),
            ("Mantenimiento de equipos eléctricos", 6), ("Montaje de tableros", 4), ("Seguridad eléctrica", 4)],
        4: [("Instalaciones eléctricas industriales", 6), ("Automatización de sistemas eléctricos", 6),
            ("Energías renovables", 4), ("Proyectos eléctricos", 4), ("Emprendimiento y empleabilidad", 4)],
    },
}


def grado_media(curso):
    nombre = curso.nivel.nombre.strip()
    m = re.match(r"^\s*([1-4])\s*°?\s*(año\s+)?medio", nombre, re.IGNORECASE)
    if m:
        return int(m.group(1))
    romanos = {"I": 1, "II": 2, "III": 3, "IV": 4}
    m = re.match(r"^\s*(IV|III|II|I)\s+medio", nombre, re.IGNORECASE)
    return romanos[m.group(1).upper()] if m else None


def _asignatura(nombre, tipo="ASIGNATURA", orden=50):
    a, _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={
        "orden": ORDEN_MEDIA.index(nombre) if nombre in ORDEN_MEDIA else orden, "tipo": tipo,
        "incide_en_promedio": nombre != "Orientación" and nombre not in CREDOS,
        "con_concepto": nombre == "Orientación", "religion": CREDOS.get(nombre, "")})
    return a


def plan_media(curso, electivos=None):
    """Lista de (nombre, horas, tipo) del plan de Media para el curso; None si no es de Media."""
    grado = grado_media(curso)
    if grado is None:
        return None
    if grado <= 2:
        return [(n, h, "ASIGNATURA") for n, h in PLAN_MEDIA["1-2"]]
    plan = [(n, h, "ASIGNATURA") for n, h in PLAN_MEDIA["3-4"]]
    if curso.modalidad == "TP" and curso.especialidad in ESPECIALIDADES_TP:
        plan += [(n, h, "MODULO_TP") for n, h in ESPECIALIDADES_TP[curso.especialidad][grado]]
    elif curso.modalidad == "HC" and electivos:
        plan += [(n, 6, "DIFERENCIADA") for n in electivos]
    return plan


def decreto_media(curso):
    grado = grado_media(curso)
    if grado is None:
        return ""
    if grado <= 2:
        return DECRETO_MEDIA_1_2
    return DECRETO_MEDIA_3_4_TP if curso.modalidad == "TP" else DECRETO_MEDIA_3_4_HC


def aplicar_plan_media(curso, electivos=None):
    plan = plan_media(curso, electivos)
    if plan is None:
        return None
    agregadas = 0
    for nombre, horas, tipo in plan:
        _, creada = AsignaturaCurso.objects.get_or_create(
            curso=curso, asignatura=_asignatura(nombre, tipo, orden=60 if tipo != "ASIGNATURA" else 50),
            defaults={"horas_semanales": horas})
        agregadas += creada
    return agregadas
