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
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .models import (
    NOTA_MAXIMA, NOTA_MINIMA, Anotacion, Asignatura, Calificacion, Curso, Estudiante, Evaluacion, Nivel,
    anio_actual,
)
from .lectores import FormatoNoSoportado, leer_filas
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


def leer_nota(valor, conceptos=False):
    """Acepta 5.5, '5,5', 55 (=5,5) y, si el curso evalúa con conceptos, MB, B, S o I (con su equivalencia).
    Devuelve Decimal o None si la celda está vacía."""
    if valor in (None, ""):
        return None
    if conceptos:
        from .calculos import EQUIVALENCIAS
        sigla = _texto(valor).strip().upper()
        if sigla in EQUIVALENCIAS:
            return EQUIVALENCIAS[sigla]
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


def _leer(archivo):
    try:
        return leer_filas(archivo)
    except FormatoNoSoportado as e:
        raise ErrorImportacion([str(e)])


def _entero(valor):
    """'1', 1, 1.0 o '1.0' -> 1."""
    return int(float(_texto(valor).replace(",", ".")))


def _filas_con_encabezado(archivo, columnas, filas=None):
    """Lee la primera tabla y devuelve [(n_fila, {campo: valor})] según el mapa de columnas."""
    filas = iter(filas if filas is not None else _leer(archivo))
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
    return indices, resultado


# --------------------------------------------------------------------------- Estudiantes

COLUMNAS_ESTUDIANTES = [
    ("RUT", "rut"), ("Nombres", "nombres"), ("Apellido paterno", "apellido_paterno"),
    ("Apellido materno", "apellido_materno"), ("Fecha nacimiento", "fecha_nacimiento"),
    ("Nivel", "nivel"), ("Letra", "letra"), ("Año", "anio"),
    ("Dirección", "direccion"), ("Comuna", "comuna"), ("Teléfono", "telefono"), ("Email", "email"),
    ("Apoderado", "apoderado_nombre"), ("RUT apoderado", "apoderado_rut"),
    ("Teléfono apoderado", "apoderado_telefono"), ("Contacto emergencia", "contacto_emergencia"),
    ("Teléfono emergencia", "telefono_emergencia"), ("Religión", "religion"),
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


def importar_estudiantes(archivo, cursos_permitidos=None):
    tabla = _leer(archivo)
    if tabla and es_nomina_sige(tabla[0]):
        return importar_nomina_sige(tabla, cursos_permitidos)
    if cursos_permitidos is not None:
        raise ErrorImportacion(["Como profesor(a) jefe solo puede subir la nómina descargada desde SIGE."])
    indices, filas = _filas_con_encabezado(archivo, _ALIAS_ESTUDIANTES, tabla)
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
            if _texto(datos.get("religion")):
                clave_rel = _clave(datos.get("religion"))
                valores["religion"] = ("CATOLICA" if clave_rel.startswith("catol") else
                                       "EVANGELICA" if clave_rel.startswith("evang") else "NO_OPTA")
            nivel_txt, letra = _texto(datos.get("nivel")), _texto(datos.get("letra")).upper()
            if nivel_txt and letra:
                try:
                    anio = _entero(datos.get("anio") or anio_actual())
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


# --------------------------------------------------------------------------- Nómina SIGE

_COLUMNAS_SIGE = {
    "ano": "anio", "anio": "anio", "codtipoensenanza": "cod_tipo", "codgrado": "cod_grado", "descgrado": "desc_grado",
    "letracurso": "letra", "run": "run", "digitover": "dv", "digitoverificador": "dv", "genero": "genero",
    "nombres": "nombres", "apellidopaterno": "apellido_paterno", "apellidomaterno": "apellido_materno",
    "direccion": "direccion", "comunaresidencia": "comuna", "email": "email", "telefono": "telefono",
    "celular": "celular", "fechanacimiento": "fecha_nacimiento", "fecharetiro": "fecha_retiro",
    "asistenca": "asistencia", "asistencia": "asistencia", "rbd": "rbd", "codigocomunaresidencia": "codigo_comuna",
    "codigoetnia": "codigo_etnia", "fechaincorporacioncurso": "fecha_incorporacion", "promediofinal": "promedio",
}
_MINUSCULAS = {"de", "del", "la", "las", "los", "y", "e", "van", "von", "da", "di"}
_ROMANOS = {1: "I", 2: "II", 3: "III", 4: "IV"}


def es_nomina_sige(encabezado):
    claves = {_clave(c) for c in encabezado}
    return {"run", "descgrado", "letracurso"} <= claves and ("digitover" in claves or "digitoverificador" in claves)


def nombre_propio(texto):
    """'JUAN DE LA CRUZ' -> 'Juan de la Cruz'."""
    palabras = _texto(texto).lower().split()
    return " ".join(p if (i and p in _MINUSCULAS) else p[:1].upper() + p[1:] for i, p in enumerate(palabras))


def nivel_canonico(cod_tipo, cod_grado, descripcion):
    """(nombre, orden, enseñanza) a partir de los códigos SIGE."""
    from .models import Nivel as N

    try:
        tipo, grado = _entero(cod_tipo), _entero(cod_grado)
    except ValueError:
        return descripcion, None, ""
    if tipo == 10:
        nombres = {1: "Sala Cuna Menor", 2: "Sala Cuna Mayor", 3: "Medio Menor", 4: "Pre-kínder", 5: "Kínder"}
        if grado in (4, 5):
            return nombres[grado], grado - 3, N.Ensenanza.PARVULARIA
        return descripcion, None, N.Ensenanza.PARVULARIA
    if 110 <= tipo < 300:
        return f"{grado}° Básico", grado + 2, N.Ensenanza.BASICA
    if tipo >= 300 and grado in _ROMANOS:
        return f"{_ROMANOS[grado]} Medio", grado + 10, N.Ensenanza.MEDIA
    return descripcion, None, ""


def reordenar_niveles():
    """Asigna el orden oficial a los niveles con nombres reconocibles (Pre-kínder, Kínder, 1° Básico…)."""
    import re

    for nivel in Nivel.objects.all():
        clave = _clave(nivel.nombre)
        orden = ensenanza = None
        if clave in ("prekinder", "nt1"):
            orden, ensenanza = 1, Nivel.Ensenanza.PARVULARIA
        elif clave in ("kinder", "nt2"):
            orden, ensenanza = 2, Nivel.Ensenanza.PARVULARIA
        elif m := re.fullmatch(r"(\d)basico", clave):
            orden, ensenanza = int(m.group(1)) + 2, Nivel.Ensenanza.BASICA
        elif m := re.fullmatch(r"([1-4])medio", clave):
            orden, ensenanza = int(m.group(1)) + 10, Nivel.Ensenanza.MEDIA
        elif m := re.fullmatch(r"(i|ii|iii|iv)medio", clave):
            orden, ensenanza = {"i": 1, "ii": 2, "iii": 3, "iv": 4}[m.group(1)] + 10, Nivel.Ensenanza.MEDIA
        if orden is not None and (nivel.orden != orden or nivel.ensenanza != ensenanza):
            nivel.orden, nivel.ensenanza = orden, ensenanza
            nivel.save(update_fields=["orden", "ensenanza"])


def importar_nomina_sige(tabla, cursos_permitidos=None):
    """Importa la nómina de estudiantes tal como la exporta SIGE (Ministerio de Educación).

    cursos_permitidos: si se indica (profesor jefe), solo se aceptan estudiantes de esos cursos.
    """
    from .models import Establecimiento

    indices, filas = _filas_con_encabezado(None, _COLUMNAS_SIGE, tabla)
    errores, creados, actualizados, retirados = [], 0, 0, 0
    cursos = {}
    rbd_propio = _texto(Establecimiento.actual().rbd).split("-")[0].strip()
    with transaction.atomic():
        for n, d in filas:
            run, dv = _texto(d.get("run")), _texto(d.get("dv"))
            if not rut_es_valido(f"{run}-{dv}"):
                errores.append(f"Fila {n}: RUN «{run}-{dv}» no válido")
                continue
            rbd = _texto(d.get("rbd")).split("-")[0].strip()
            if rbd_propio and rbd and rbd != rbd_propio:
                errores.append(f"Fila {n}: el RBD {rbd} no corresponde a este establecimiento (RBD {rbd_propio})")
                continue
            try:
                anio = _entero(d.get("anio") or anio_actual())
                nacimiento = _fecha(d.get("fecha_nacimiento"))
                retiro = _fecha(d.get("fecha_retiro"))
                incorporacion = _fecha(d.get("fecha_incorporacion"))
            except ValueError as e:
                errores.append(f"Fila {n}: {e}")
                continue
            if retiro is not None and retiro.year <= 1900:
                retiro = None
            if incorporacion is not None and incorporacion.year <= 1900:
                incorporacion = None
            clave_curso = (_texto(d.get("cod_tipo")), _texto(d.get("cod_grado")), _texto(d.get("desc_grado")),
                           _texto(d.get("letra")).upper(), anio)
            if clave_curso not in cursos:
                nombre, orden, ensenanza = nivel_canonico(*clave_curso[:3])
                nivel = Nivel.objects.filter(nombre__iexact=nombre).first()
                if nivel is None:
                    if orden is None:
                        orden = (Nivel.objects.aggregate(m=Max("orden"))["m"] or 0) + 1
                    nivel = Nivel.objects.create(nombre=nombre, orden=orden, ensenanza=ensenanza)
                cursos[clave_curso], creado = Curso.objects.get_or_create(nivel=nivel, letra=clave_curso[3] or "A", anio=anio)
                try:  # Media: código SIGE 310 = Científico-Humanista; 410 en adelante = Técnico-Profesional
                    tipo_sige = _entero(clave_curso[0])
                except ValueError:
                    tipo_sige = 0
                if ensenanza == Nivel.Ensenanza.MEDIA and not cursos[clave_curso].modalidad and tipo_sige >= 310:
                    cursos[clave_curso].modalidad = "HC" if tipo_sige < 400 else "TP"
                    cursos[clave_curso].save(update_fields=["modalidad"])
            asistencia = None
            try:
                valor = Decimal(_texto(d.get("asistencia")).replace(",", ".") or "0")
                asistencia = valor if 0 < valor <= 100 else None
            except InvalidOperation:
                pass
            if cursos_permitidos is not None and cursos[clave_curso] not in cursos_permitidos:
                errores.append(f"Fila {n}: el curso {cursos[clave_curso].nombre_corto} no es de su jefatura")
                continue
            activo = retiro is None
            try:
                promedio = Decimal(_texto(d.get("promedio")).replace(",", ".") or "0")
                promedio = promedio if Decimal("1") <= promedio <= Decimal("7") else None
            except InvalidOperation:
                promedio = None
            valores = {
                "nombres": nombre_propio(d.get("nombres")),
                "apellido_paterno": nombre_propio(d.get("apellido_paterno")),
                "apellido_materno": nombre_propio(d.get("apellido_materno")),
                "fecha_nacimiento": nacimiento, "curso": cursos[clave_curso], "activo": activo,
                "genero": _texto(d.get("genero")).upper()[:1] if _texto(d.get("genero")).upper()[:1] in ("F", "M") else "",
            }
            valores.update({"fecha_retiro": retiro, "fecha_incorporacion": incorporacion,
                            "codigo_etnia": _texto(d.get("codigo_etnia")), "promedio_sige": promedio})
            if _texto(d.get("codigo_comuna")):
                valores["codigo_comuna"] = _texto(d.get("codigo_comuna"))
            for campo, origen in (("direccion", "direccion"), ("email", "email")):
                if _texto(d.get(origen)):
                    valores[campo] = nombre_propio(d.get(origen)) if campo == "direccion" else _texto(d.get(origen)).lower()
            if _texto(d.get("comuna")):
                valores["comuna"] = nombre_propio(d.get("comuna"))
            for campo in ("telefono", "celular"):
                if _texto(d.get(campo)) not in ("", "0"):
                    valores[campo] = _texto(d.get(campo))
            if asistencia is not None and not _usa_libro(cursos[clave_curso]):
                valores["porcentaje_asistencia"] = asistencia  # si el curso usa el libro digital, manda el libro
            if not valores["nombres"] or not valores["apellido_paterno"]:
                errores.append(f"Fila {n}: faltan nombres o apellido paterno")
                continue
            _, creado = Estudiante.objects.update_or_create(rut=normalizar_rut(f"{run}-{dv}"), defaults=valores)
            creados += creado
            actualizados += not creado
            retirados += not activo
        if errores:
            transaction.set_rollback(True)
            raise ErrorImportacion(errores)
        reordenar_niveles()
    return {"creados": creados, "actualizados": actualizados, "cursos": len(set(cursos.values())),
            "retirados": retirados, "sige": True}


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
    from .calculos import usa_conceptos

    tabla = _leer(archivo)
    con_conceptos = usa_conceptos(asignatura_curso.curso)

    def celda(fila, col):  # fila y columna desde 1, como en Excel
        if fila - 1 < len(tabla) and col - 1 < len(tabla[fila - 1]):
            return tabla[fila - 1][col - 1]
        return None

    max_col = max((len(f) for f in tabla), default=0)
    errores = []
    columnas = []  # (indice_columna, evaluacion)
    evaluaciones = {(e.nombre.strip().lower(), e.semestre): e for e in asignatura_curso.evaluaciones.all()}
    estudiantes = {e.rut: e for e in asignatura_curso.curso.estudiantes.all() if e.cursa(asignatura_curso.asignatura)}
    guardadas = 0
    with transaction.atomic():
        for col in range(3, max_col + 1):
            nombre = _texto(celda(1, col))
            if not nombre:
                continue
            try:
                semestre = _entero(celda(FILA_SEMESTRE, col) or 1)
                if semestre not in (1, 2):
                    raise ValueError
            except ValueError:
                errores.append(f"Columna «{nombre}»: el semestre debe ser 1 o 2")
                continue
            try:
                ponderacion = Decimal(_texto(celda(FILA_PONDERACION, col)).replace(",", ".") or "1")
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

        for fila in range(PRIMERA_FILA_ESTUDIANTE, len(tabla) + 1):
            rut = _texto(celda(fila, 1))
            if not rut:
                continue
            est = estudiantes.get(normalizar_rut(rut)) if rut_es_valido(rut) else None
            if est is None:
                errores.append(f"Fila {fila}: el RUT «{rut}» no corresponde a un estudiante del curso")
                continue
            for col, ev in columnas:
                try:
                    nota = leer_nota(celda(fila, col), conceptos=con_conceptos)
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
    for est in [e for e in asignatura_curso.curso.estudiantes.filter(activo=True) if e.cursa(asignatura_curso.asignatura)]:
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


def _usa_libro(curso):
    from .libro import curso_usa_libro

    return curso.pk is not None and curso_usa_libro(curso)


# --------------------------------------------------------------------------- Currículum (OA propios)

def importar_oas(archivo):
    """Importa OA propios del establecimiento. Columnas: Asignatura, Nivel, OA, Texto (y opcional Unidad)."""
    from .curriculo import clave_asignatura, grado_desde_texto
    from .models import Establecimiento, ObjetivoAprendizaje

    columnas = {"asignatura": "asignatura", "nivel": "nivel", "curso": "nivel", "oa": "numero", "numero": "numero",
                "n": "numero", "texto": "texto", "objetivo": "texto", "objetivodeaprendizaje": "texto",
                "unidad": "unidad"}
    try:
        indices, filas = _filas_con_encabezado(archivo, columnas)
    except ErrorImportacion as e:
        raise ValueError(str(e))
    faltan = {"asignatura", "nivel", "numero", "texto"} - set(indices)
    if faltan:
        raise ValueError("El archivo debe tener las columnas Asignatura, Nivel, OA y Texto.")
    from .models import Asignatura

    est = Establecimiento.actual()
    propias = {a.nombre.strip().lower(): a for a in Asignatura.objects.all()}
    errores, n = [], 0
    with transaction.atomic():
        for fila, d in filas:
            nivel = _texto(d["nivel"])
            grado = 0 if nivel.strip().lower() in ("todos", "todos los niveles", "-", "") else grado_desde_texto(nivel)
            try:
                numero = int(re.sub(r"\D", "", _texto(d["numero"])) or "x")
            except ValueError:
                numero = None
            texto = _texto(d["texto"])
            if grado is None or not numero or not texto:
                errores.append(f"Fila {fila}: revise nivel (ej. «5° básico», «I medio»), N° de OA y texto.")
                continue
            nombre = _texto(d["asignatura"])
            clave = clave_asignatura(nombre)
            propia = propias.get(nombre.strip().lower())
            if propia is not None and propia.tipo == Asignatura.Tipo.ASIGNATURA and clave != "otra":
                propia = None  # asignatura del currículum nacional: OA complementario de esa asignatura
            if propia is not None and propia.tipo != Asignatura.Tipo.ASIGNATURA:
                clave = "otra"
            if grado == 0 and propia is None:
                errores.append(f"Fila {fila}: «Todos los niveles» solo se usa con un taller o módulo del establecimiento.")
                continue
            ObjetivoAprendizaje.objects.update_or_create(
                establecimiento=est, asignatura=clave, asignatura_propia=propia, grado=grado, numero=numero,
                defaults={"texto": texto, "unidad": _texto(d.get("unidad"))[:120]})
            n += 1
        if errores:
            transaction.set_rollback(True)
            raise ValueError(" ".join(errores[:10]))
    return n
