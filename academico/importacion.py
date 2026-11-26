"""Carga masiva desde Excel (.xlsx) y generación de plantillas.

Cada importación es "todo o nada": si alguna fila tiene errores no se guarda nada
y se informa la lista de errores (fila y motivo).
"""
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db import transaction
from django.db.models import Max
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .models import (
    NOTA_MAXIMA, NOTA_MINIMA, Anotacion, Asignatura, Calificacion, Curso, Estudiante, Evaluacion, Nivel,
    anio_actual,
)
from .rut import normalizar_rut, rut_es_valido


class ErrorImportacion(Exception):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores))


def _clave(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _fecha(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    texto = _texto(valor)
    for formato in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"fecha «{texto}» no reconocida (use dd-mm-aaaa)")


def leer_nota(valor):
    """Acepta 5.5, '5,5', 55 (=5,5). Devuelve Decimal o None si la celda está vacía."""
    if valor in (None, ""):
        return None
    texto = _texto(valor).replace(",", ".")
    try:
        nota = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"«{_texto(valor)}» no es una nota")
    if Decimal("10") <= nota <= Decimal("70") and nota == nota.to_integral_value():
        nota = nota / 10  # notas escritas sin punto: 55 -> 5,5
    nota = nota.quantize(Decimal("0.1"))
    if not (NOTA_MINIMA <= nota <= NOTA_MAXIMA):
        raise ValueError(f"la nota {texto} está fuera del rango 1,0 – 7,0")
    return nota


def _filas_con_encabezado(archivo, columnas):
    """Lee la primera hoja y devuelve [(n_fila, {campo: valor})] según el mapa de columnas."""
    libro = load_workbook(archivo, data_only=True, read_only=True)
    hoja = libro.worksheets[0]
    filas = hoja.iter_rows(values_only=True)
    encabezado = next(filas, None) or []
    indices = {}
    for i, titulo in enumerate(encabezado):
        campo = columnas.get(_clave(titulo))
        if campo and campo not in indices:
            indices[campo] = i
    resultado = []
    for n, fila in enumerate(filas, start=2):
        if not fila or all(v in (None, "") for v in fila):
            continue
        resultado.append((n, {c: (fila[i] if i < len(fila) else None) for c, i in indices.items()}))
    libro.close()
    return indices, resultado


# --------------------------------------------------------------------------- Estudiantes

COLUMNAS_ESTUDIANTES = [
    ("RUT", "rut"), ("Nombres", "nombres"), ("Apellido paterno", "apellido_paterno"),
    ("Apellido materno", "apellido_materno"), ("Fecha nacimiento", "fecha_nacimiento"),
    ("Nivel", "nivel"), ("Letra", "letra"), ("Año", "anio"),
    ("Dirección", "direccion"), ("Comuna", "comuna"), ("Teléfono", "telefono"), ("Email", "email"),
    ("Apoderado", "apoderado_nombre"), ("RUT apoderado", "apoderado_rut"),
    ("Teléfono apoderado", "apoderado_telefono"), ("Contacto emergencia", "contacto_emergencia"),
    ("Teléfono emergencia", "telefono_emergencia"),
]
_ALIAS_ESTUDIANTES = {_clave(t): c for t, c in COLUMNAS_ESTUDIANTES}
_ALIAS_ESTUDIANTES.update({
    "fechadenacimiento": "fecha_nacimiento", "anio": "anio", "ano": "anio", "curso": "letra",
    "correo": "email", "correoelectronico": "email", "nombreapoderado": "apoderado_nombre",
    "telefonodelapoderado": "apoderado_telefono", "celular": "telefono",
})
CAMPOS_TEXTO_ESTUDIANTE = [
    "nombres", "apellido_paterno", "apellido_materno", "direccion", "comuna", "telefono", "email",
    "apoderado_nombre", "apoderado_telefono", "contacto_emergencia", "telefono_emergencia",
]


def importar_estudiantes(archivo):
    indices, filas = _filas_con_encabezado(archivo, _ALIAS_ESTUDIANTES)
    faltantes = [c for c in ("rut", "nombres", "apellido_paterno") if c not in indices]
    if faltantes:
        raise ErrorImportacion([f"Falta la columna obligatoria: {', '.join(faltantes)}"])

    errores, creados, actualizados = [], 0, 0
    vistos = set()
    with transaction.atomic():
        for n, datos in filas:
            rut = _texto(datos.get("rut"))
            if not rut_es_valido(rut):
                errores.append(f"Fila {n}: RUT «{rut}» no válido")
                continue
            rut = normalizar_rut(rut)
            if rut in vistos:
                errores.append(f"Fila {n}: RUT {rut} repetido en el archivo")
                continue
            vistos.add(rut)
            valores = {c: _texto(datos.get(c)) for c in CAMPOS_TEXTO_ESTUDIANTE if c in indices}
            if not valores.get("nombres") or not valores.get("apellido_paterno"):
                errores.append(f"Fila {n}: faltan nombres o apellido paterno")
                continue
            try:
                if "fecha_nacimiento" in indices:
                    valores["fecha_nacimiento"] = _fecha(datos.get("fecha_nacimiento"))
            except ValueError as e:
                errores.append(f"Fila {n}: {e}")
                continue
            rut_apod = _texto(datos.get("apoderado_rut"))
            if rut_apod:
                if not rut_es_valido(rut_apod):
                    errores.append(f"Fila {n}: RUT de apoderado «{rut_apod}» no válido")
                    continue
                valores["apoderado_rut"] = normalizar_rut(rut_apod)
            nivel_txt, letra = _texto(datos.get("nivel")), _texto(datos.get("letra")).upper()
            if nivel_txt and letra:
                try:
                    anio = int(_texto(datos.get("anio")) or anio_actual())
                except ValueError:
                    errores.append(f"Fila {n}: año «{datos.get('anio')}» no válido")
                    continue
                valores["curso"] = _obtener_curso(nivel_txt, letra, anio)
            elif nivel_txt or letra:
                errores.append(f"Fila {n}: indique Nivel y Letra del curso (ambos)")
                continue
            _, creado = Estudiante.objects.update_or_create(rut=rut, defaults=valores)
            creados += creado
            actualizados += not creado
        if errores:
            transaction.set_rollback(True)
            raise ErrorImportacion(errores)
    return {"creados": creados, "actualizados": actualizados}


def _obtener_curso(nivel_txt, letra, anio):
    nivel = Nivel.objects.filter(nombre__iexact=nivel_txt).first()
    if nivel is None:
        orden = (Nivel.objects.aggregate(m=Max("orden"))["m"] or 0) + 1
        nivel = Nivel.objects.create(nombre=nivel_txt, orden=orden)
    curso, _ = Curso.objects.get_or_create(nivel=nivel, letra=letra, anio=anio)
    return curso


# --------------------------------------------------------------------------- Notas

FILA_SEMESTRE, FILA_PONDERACION, PRIMERA_FILA_ESTUDIANTE = 2, 3, 4


def importar_notas(archivo, asignatura_curso):
    """Formato (el mismo de la plantilla descargable):
    fila 1: RUT | Estudiante | <nombre evaluación> ...
    fila 2: Semestre | | 1 o 2 ...
    fila 3: Ponderación | | peso ...
    fila 4 en adelante: rut | nombre | notas
    """
    libro = load_workbook(archivo, data_only=True)
    hoja = libro.worksheets[0]
    errores = []
    columnas = []  # (indice_columna, evaluacion)
    evaluaciones = {(e.nombre.strip().lower(), e.semestre): e for e in asignatura_curso.evaluaciones.all()}
    estudiantes = {e.rut: e for e in asignatura_curso.curso.estudiantes.all()}
    guardadas = 0
    with transaction.atomic():
        for col in range(3, hoja.max_column + 1):
            nombre = _texto(hoja.cell(1, col).value)
            if not nombre:
                continue
            try:
                semestre = int(_texto(hoja.cell(FILA_SEMESTRE, col).value) or 1)
                if semestre not in (1, 2):
                    raise ValueError
            except ValueError:
                errores.append(f"Columna «{nombre}»: el semestre debe ser 1 o 2")
                continue
            try:
                ponderacion = Decimal(_texto(hoja.cell(FILA_PONDERACION, col).value).replace(",", ".") or "1")
                if ponderacion <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                errores.append(f"Columna «{nombre}»: ponderación no válida")
                continue
            ev = evaluaciones.get((nombre.lower(), semestre))
            if ev is None:
                ev = Evaluacion.objects.create(
                    asignatura_curso=asignatura_curso, nombre=nombre, semestre=semestre, ponderacion=ponderacion
                )
                evaluaciones[(nombre.lower(), semestre)] = ev
            elif ev.ponderacion != ponderacion:
                ev.ponderacion = ponderacion
                ev.save(update_fields=["ponderacion"])
            columnas.append((col, ev))

        for fila in range(PRIMERA_FILA_ESTUDIANTE, hoja.max_row + 1):
            rut = _texto(hoja.cell(fila, 1).value)
            if not rut:
                continue
            est = estudiantes.get(normalizar_rut(rut)) if rut_es_valido(rut) else None
            if est is None:
                errores.append(f"Fila {fila}: el RUT «{rut}» no corresponde a un estudiante del curso")
                continue
            for col, ev in columnas:
                try:
                    nota = leer_nota(hoja.cell(fila, col).value)
                except ValueError as e:
                    errores.append(f"Fila {fila}, «{ev.nombre}»: {e}")
                    continue
                if nota is None:
                    continue
                Calificacion.objects.update_or_create(evaluacion=ev, estudiante=est, defaults={"nota": nota})
                guardadas += 1
        if errores:
            transaction.set_rollback(True)
            raise ErrorImportacion(errores)
    return {"notas": guardadas, "evaluaciones": len(columnas)}


# --------------------------------------------------------------------------- Anotaciones

COLUMNAS_ANOTACIONES = [
    ("RUT", "rut"), ("Fecha", "fecha"), ("Tipo", "tipo"), ("Gravedad", "gravedad"),
    ("Asignatura", "asignatura"), ("Descripción", "descripcion"), ("Medida", "medida"),
]
_ALIAS_ANOTACIONES = {_clave(t): c for t, c in COLUMNAS_ANOTACIONES}
_ALIAS_ANOTACIONES.update({"anotacion": "descripcion", "observacion": "descripcion", "medidatomada": "medida"})


def _elegir(valor, opciones, campo):
    clave = _clave(valor)
    for codigo, etiqueta in opciones:
        if clave in (_clave(codigo), _clave(etiqueta)):
            return codigo
    raise ValueError(f"{campo} «{valor}» no válido (use: {', '.join(e for _, e in opciones)})")


def importar_anotaciones(archivo, estudiantes_permitidos, autor):
    indices, filas = _filas_con_encabezado(archivo, _ALIAS_ANOTACIONES)
    faltantes = [c for c in ("rut", "descripcion") if c not in indices]
    if faltantes:
        raise ErrorImportacion([f"Falta la columna obligatoria: {', '.join(faltantes)}"])
    asignaturas = {_clave(a.nombre): a for a in Asignatura.objects.all()}
    errores, creadas = [], 0
    with transaction.atomic():
        for n, datos in filas:
            try:
                rut = _texto(datos.get("rut"))
                est = estudiantes_permitidos.filter(rut=normalizar_rut(rut)).first() if rut_es_valido(rut) else None
                if est is None:
                    raise ValueError(f"RUT «{rut}» no encontrado o sin acceso")
                descripcion = _texto(datos.get("descripcion"))
                if not descripcion:
                    raise ValueError("falta la descripción")
                tipo = _elegir(_texto(datos.get("tipo")) or "Observación", Anotacion.Tipo.choices, "Tipo")
                gravedad = ""
                if tipo == Anotacion.Tipo.NEGATIVA and _texto(datos.get("gravedad")):
                    gravedad = _elegir(_texto(datos.get("gravedad")), Anotacion.Gravedad.choices, "Gravedad")
                asignatura = None
                if _texto(datos.get("asignatura")):
                    asignatura = asignaturas.get(_clave(datos.get("asignatura")))
                    if asignatura is None:
                        raise ValueError(f"asignatura «{_texto(datos.get('asignatura'))}» no existe")
                Anotacion.objects.create(
                    estudiante=est, fecha=_fecha(datos.get("fecha")) or dt.date.today(), tipo=tipo,
                    gravedad=gravedad, asignatura=asignatura, descripcion=descripcion,
                    medida=_texto(datos.get("medida")), autor=autor,
                )
                creadas += 1
            except ValueError as e:
                errores.append(f"Fila {n}: {e}")
        if errores:
            transaction.set_rollback(True)
            raise ErrorImportacion(errores)
    return {"creadas": creadas}


# --------------------------------------------------------------------------- Plantillas

_NEGRITA = Font(bold=True, color="FFFFFF")
_RELLENO = PatternFill("solid", fgColor="1F4E79")
_RELLENO_SUAVE = PatternFill("solid", fgColor="DDEBF7")


def _libro_a_bytes(libro):
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _encabezado(hoja, titulos):
    hoja.append(titulos)
    for celda in hoja[1]:
        celda.font, celda.fill = _NEGRITA, _RELLENO
    for i, t in enumerate(titulos, start=1):
        hoja.column_dimensions[hoja.cell(1, i).column_letter].width = max(14, len(t) + 4)
    hoja.freeze_panes = "A2"


def plantilla_estudiantes():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Estudiantes"
    _encabezado(hoja, [t for t, _ in COLUMNAS_ESTUDIANTES])
    hoja.append([
        "12.345.678-5", "Juan Andrés", "Pérez", "González", "15-03-2015", "4° Básico", "A", anio_actual(),
        "Av. Siempre Viva 123", "Santiago", "+56 9 1234 5678", "familia@correo.cl",
        "María González", "9.876.543-3", "+56 9 8765 4321", "Abuela Rosa", "+56 2 2345 6789",
    ])
    ayuda = libro.create_sheet("Instrucciones")
    for linea in [
        "Una fila por estudiante. RUT, Nombres y Apellido paterno son obligatorios.",
        "Si el RUT ya existe, los datos del estudiante se actualizan.",
        "Nivel y Letra asignan el curso (se crea si no existe). Año: por defecto el año actual.",
        "Fechas en formato dd-mm-aaaa. Borre la fila de ejemplo antes de importar.",
    ]:
        ayuda.append([linea])
    ayuda.column_dimensions["A"].width = 100
    return _libro_a_bytes(libro)


def plantilla_notas(asignatura_curso):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Notas"
    evaluaciones = list(asignatura_curso.evaluaciones.all())
    if not evaluaciones:
        evaluaciones = [Evaluacion(nombre="Nota 1", semestre=1), Evaluacion(nombre="Nota 2", semestre=1)]
    hoja.append(["RUT", "Estudiante"] + [e.nombre for e in evaluaciones])
    hoja.append(["Semestre (1 o 2)", ""] + [e.semestre for e in evaluaciones])
    hoja.append(["Ponderación", ""] + [float(e.ponderacion) for e in evaluaciones])
    for celda in hoja[1]:
        celda.font, celda.fill = _NEGRITA, _RELLENO
    for fila in (2, 3):
        for celda in hoja[fila]:
            celda.fill = _RELLENO_SUAVE
    notas = {
        (c.estudiante_id, c.evaluacion_id): float(c.nota)
        for c in Calificacion.objects.filter(evaluacion__in=[e for e in evaluaciones if e.pk])
    }
    for est in asignatura_curso.curso.estudiantes.filter(activo=True):
        hoja.append([est.rut_formateado, est.nombre_completo] + [notas.get((est.id, e.pk)) for e in evaluaciones])
    hoja.column_dimensions["A"].width = 16
    hoja.column_dimensions["B"].width = 38
    for i in range(3, len(evaluaciones) + 13):
        hoja.column_dimensions[hoja.cell(1, i).column_letter].width = 13
    validacion = DataValidation(type="decimal", operator="between", formula1="1", formula2="7",
                                error="La nota debe estar entre 1,0 y 7,0", showErrorMessage=True)
    hoja.add_data_validation(validacion)
    validacion.add(f"C{PRIMERA_FILA_ESTUDIANTE}:Z{max(hoja.max_row, PRIMERA_FILA_ESTUDIANTE)}")
    hoja.freeze_panes = "C4"
    ayuda = libro.create_sheet("Instrucciones")
    for linea in [
        f"Asignatura: {asignatura_curso}",
        "Agregue una columna por evaluación: nombre en la fila 1, semestre (1 o 2) en la fila 2 y ponderación en la fila 3.",
        "La ponderación es un peso relativo dentro del semestre (1 = todas iguales; o porcentajes como 30 y 70).",
        "Notas de 1,0 a 7,0. Las celdas vacías se ignoran (no borran notas existentes).",
        "No modifique la columna RUT.",
    ]:
        ayuda.append([linea])
    ayuda.column_dimensions["A"].width = 110
    return _libro_a_bytes(libro)


def plantilla_anotaciones():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Anotaciones"
    _encabezado(hoja, [t for t, _ in COLUMNAS_ANOTACIONES])
    hoja.column_dimensions["F"].width = 60
    hoja.append(["12.345.678-5", "20-05-2026", "Negativa", "Leve", "Matemática",
                 "Interrumpe la clase reiteradamente.", "Conversación con el estudiante"])
    hoja.append(["12.345.678-5", "22-05-2026", "Positiva", "", "", "Ayuda a sus compañeros.", ""])
    ayuda = libro.create_sheet("Instrucciones")
    for linea in [
        "Tipo: Positiva, Negativa u Observación. Gravedad (solo negativas): Leve, Grave o Gravísima.",
        "Asignatura es opcional y debe coincidir con el nombre registrado en la plataforma.",
        "Borre las filas de ejemplo antes de importar.",
    ]:
        ayuda.append([linea])
    ayuda.column_dimensions["A"].width = 100
    return _libro_a_bytes(libro)
