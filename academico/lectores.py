"""Lectura de planillas en distintos formatos como una lista de filas.

Formatos aceptados:
- Excel .xlsx y .xls (incluido el ".xls" que exporta SIGE, que en realidad es una página HTML)
- CSV / TXT separado por coma, punto y coma o tabulación (UTF-8 o Latin-1)
- Páginas HTML (.html, .htm) con una tabla
- Word .docx: se lee la primera tabla del documento
"""
import csv
import io
import os

EXTENSIONES = (".xlsx", ".xls", ".csv", ".txt", ".html", ".htm", ".docx")


class FormatoNoSoportado(Exception):
    pass


def _decodificar(datos: bytes) -> str:
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1", errors="replace")


def _es_html(datos: bytes) -> bool:
    inicio = datos[:2048].lstrip().lower()
    return inicio.startswith(b"<!doctype html") or inicio.startswith(b"<html") or b"<table" in inicio


def _leer_html(datos: bytes):
    import lxml.html

    texto = datos.decode("latin-1") if b"iso-8859-1" in datos[:3000].lower() else _decodificar(datos)
    documento = lxml.html.fromstring(texto)
    tablas = documento.xpath("//table")
    if not tablas:
        raise FormatoNoSoportado("El archivo no contiene ninguna tabla.")
    tabla = max(tablas, key=lambda t: len(t.xpath(".//tr")))  # la tabla con más filas
    filas = []
    for tr in tabla.xpath(".//tr"):
        celdas = [" ".join(c.text_content().split()) for c in tr.xpath("./td|./th")]
        filas.append(celdas)
    return filas


def _leer_csv(datos: bytes):
    texto = _decodificar(datos)
    muestra = texto[:5000]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=";,\t|")
        separador = dialecto.delimiter
    except csv.Error:
        separador = ";" if muestra.count(";") > muestra.count(",") else ","
    return [fila for fila in csv.reader(io.StringIO(texto), delimiter=separador)]


def _leer_xlsx(datos: bytes):
    from openpyxl import load_workbook

    libro = load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
    filas = [list(f) for f in libro.worksheets[0].iter_rows(values_only=True)]
    libro.close()
    return filas


def _leer_xls(datos: bytes):
    import xlrd

    libro = xlrd.open_workbook(file_contents=datos)
    hoja = libro.sheet_by_index(0)
    filas = []
    for i in range(hoja.nrows):
        fila = []
        for celda in hoja.row(i):
            if celda.ctype == xlrd.XL_CELL_DATE:
                fila.append(xlrd.xldate.xldate_as_datetime(celda.value, libro.datemode))
            else:
                fila.append(celda.value)
        filas.append(fila)
    return filas


def _leer_docx(datos: bytes):
    import docx

    documento = docx.Document(io.BytesIO(datos))
    if not documento.tables:
        raise FormatoNoSoportado("El documento Word no contiene tablas.")
    tabla = max(documento.tables, key=lambda t: len(t.rows))
    return [[" ".join(c.text.split()) for c in fila.cells] for fila in tabla.rows]


def leer_filas(archivo):
    """Devuelve la primera tabla del archivo como lista de filas (listas de valores)."""
    nombre = getattr(archivo, "name", "") or ""
    extension = os.path.splitext(nombre.lower())[1]
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    datos = archivo.read()
    if datos[:4] == b"PK\x03\x04":  # zip: xlsx o docx
        if extension == ".docx" or b"word/" in datos[:4000]:
            return _leer_docx(datos)
        return _leer_xlsx(datos)
    if datos[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":  # formato binario de Office antiguo
        if extension == ".doc":
            raise FormatoNoSoportado("Los archivos .doc antiguos no se pueden leer: guárdelo como .docx o .xlsx.")
        return _leer_xls(datos)
    if _es_html(datos):
        return _leer_html(datos)
    if extension in (".csv", ".txt", ""):
        return _leer_csv(datos)
    if extension == ".xls":
        return _leer_csv(datos)  # algunos sistemas exportan texto tabulado con extensión .xls
    raise FormatoNoSoportado(f"Formato no reconocido ({extension or 'sin extensión'}).")
