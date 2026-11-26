"""Exportación de informes en Excel (.xlsx) y PDF."""
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .calculos import concepto, formato_nota, nota_en_palabras, resumen_curso
from .models import NOTA_APROBACION, Establecimiento

AZUL = colors.HexColor("#1F4E79")
ROJO = colors.HexColor("#C00000")
GRIS = colors.HexColor("#F2F2F2")

# --------------------------------------------------------------------------- Excel

_ENC_FONT = Font(bold=True, color="FFFFFF")
_ENC_FILL = PatternFill("solid", fgColor="1F4E79")
_ROJO_XL = Font(color="C00000")


def _xl_nota(valor):
    return float(valor) if valor is not None else None


def _xl_encabezado(hoja, fila, titulos):
    for col, t in enumerate(titulos, start=1):
        c = hoja.cell(fila, col, t)
        c.font, c.fill = _ENC_FONT, _ENC_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _xl_titulo(hoja, titulo, subtitulo):
    est = Establecimiento.actual()
    hoja["A1"] = est.nombre
    hoja["A1"].font = Font(bold=True, size=13)
    hoja["A2"] = titulo
    hoja["A2"].font = Font(bold=True, size=12)
    hoja["A3"] = f"{subtitulo} · Emitido el {timezone.localdate():%d-%m-%Y}"


def _xl_pintar_notas(hoja, fila_ini, col_ini):
    for fila in hoja.iter_rows(min_row=fila_ini, min_col=col_ini):
        for c in fila:
            if isinstance(c.value, (int, float)):
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="center")
                if c.value < float(NOTA_APROBACION):
                    c.font = _ROJO_XL


def _bytes(libro):
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def excel_notas_asignatura(ac):
    asigs, evaluaciones, resumenes = resumen_curso(ac.curso, [ac])
    evs = evaluaciones[ac.id]
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Notas"
    profesor = ac.profesor.get_full_name() if ac.profesor else "—"
    _xl_titulo(hoja, f"Informe de notas – {ac.asignatura}", f"Curso {ac.curso} · Profesor(a): {profesor}")
    titulos = ["N°", "RUT", "Estudiante"]
    for s in (1, 2):
        titulos += [f"{e.nombre} (S{s})" for e in evs if e.semestre == s] + [f"Promedio S{s}"]
    titulos.append("Promedio final")
    _xl_encabezado(hoja, 5, titulos)
    for i, r in enumerate(resumenes, start=1):
        pa = r.asignaturas[0]
        fila = [i, r.estudiante.rut_formateado, r.estudiante.nombre_completo]
        for s, prom in ((1, pa.s1), (2, pa.s2)):
            fila += [_xl_nota(pa.notas.get(e.id)) for e in evs if e.semestre == s] + [_xl_nota(prom)]
        fila.append(_xl_nota(pa.final))
        hoja.append(fila)
    _xl_pintar_notas(hoja, 6, 4)
    hoja.column_dimensions["B"].width = 14
    hoja.column_dimensions["C"].width = 36
    hoja.freeze_panes = "D6"
    return _bytes(libro)


def excel_informe_final_curso(curso):
    asigs, _, resumenes = resumen_curso(curso)
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Informe final"
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else "—"
    _xl_titulo(hoja, f"Informe final de calificaciones – {curso}", f"Profesor(a) jefe: {jefe}")
    _xl_encabezado(hoja, 5, ["N°", "RUT", "Estudiante"] + [str(a.asignatura) for a in asigs]
                   + ["Promedio general", "Situación final"])
    for i, r in enumerate(resumenes, start=1):
        hoja.append([i, r.estudiante.rut_formateado, r.estudiante.nombre_completo]
                    + [_xl_nota(p.final) if p.incide else concepto(p.final) for p in r.asignaturas]
                    + [_xl_nota(r.promedio_general), r.situacion])
    _xl_pintar_notas(hoja, 6, 4)
    hoja.row_dimensions[5].height = 45
    hoja.column_dimensions["C"].width = 36
    hoja.column_dimensions["B"].width = 14
    hoja.freeze_panes = "D6"

    detalle = libro.create_sheet("Detalle semestral")
    titulos = ["RUT", "Estudiante"]
    for a in asigs:
        titulos += [f"{a.asignatura} S1", f"{a.asignatura} S2", f"{a.asignatura} Final"]
    _xl_encabezado(detalle, 1, titulos + ["Prom. S1", "Prom. S2", "Prom. general"])
    for r in resumenes:
        fila = [r.estudiante.rut_formateado, r.estudiante.nombre_completo]
        for p in r.asignaturas:
            fila += [_xl_nota(p.s1), _xl_nota(p.s2), _xl_nota(p.final)]
        detalle.append(fila + [_xl_nota(r.promedio_s1), _xl_nota(r.promedio_s2), _xl_nota(r.promedio_general)])
    _xl_pintar_notas(detalle, 2, 3)
    detalle.row_dimensions[1].height = 45
    detalle.column_dimensions["B"].width = 36
    detalle.freeze_panes = "C2"
    return _bytes(libro)


def excel_estudiantes(estudiantes):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Estudiantes"
    titulos = ["RUT", "Apellido paterno", "Apellido materno", "Nombres", "Curso", "Fecha nacimiento", "Género",
               "Dirección", "Comuna", "Teléfono", "Celular", "Email", "Apoderado", "RUT apoderado",
               "Teléfono apoderado", "Contacto emergencia", "Teléfono emergencia", "% asistencia",
               "Fecha incorporación", "Fecha retiro", "Activo"]
    _xl_encabezado(hoja, 1, titulos)
    for e in estudiantes.select_related("curso__nivel"):
        hoja.append([
            e.rut_formateado, e.apellido_paterno, e.apellido_materno, e.nombres,
            e.curso.nombre_corto if e.curso else "", e.fecha_nacimiento.strftime("%d-%m-%Y") if e.fecha_nacimiento else "",
            e.genero, e.direccion, e.comuna, e.telefono, e.celular, e.email, e.apoderado_nombre, e.apoderado_rut,
            e.apoderado_telefono, e.contacto_emergencia, e.telefono_emergencia,
            float(e.porcentaje_asistencia) if e.porcentaje_asistencia is not None else None,
            e.fecha_incorporacion.strftime("%d-%m-%Y") if e.fecha_incorporacion else "",
            e.fecha_retiro.strftime("%d-%m-%Y") if e.fecha_retiro else "", "Sí" if e.activo else "No",
        ])
    for col in "ABCDEFGHIJKLMNOPQRSTU":
        hoja.column_dimensions[col].width = 18
    hoja.freeze_panes = "A2"
    return _bytes(libro)


def excel_anotaciones(anotaciones, titulo):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Anotaciones"
    _xl_titulo(hoja, "Registro de convivencia escolar", titulo)
    _xl_encabezado(hoja, 5, ["Fecha", "RUT", "Estudiante", "Curso", "Tipo", "Gravedad", "Asignatura",
                             "Descripción", "Medida", "Registrada por"])
    for a in anotaciones.select_related("estudiante__curso__nivel", "asignatura", "autor"):
        hoja.append([
            a.fecha.strftime("%d-%m-%Y"), a.estudiante.rut_formateado, a.estudiante.nombre_completo,
            a.estudiante.curso.nombre_corto if a.estudiante.curso else "", a.get_tipo_display(),
            a.get_gravedad_display(), str(a.asignatura or ""), a.descripcion, a.medida,
            a.autor.get_full_name() if a.autor else "",
        ])
    for col, ancho in zip("ABCDEFGHIJ", (12, 14, 32, 14, 12, 12, 18, 60, 40, 24)):
        hoja.column_dimensions[col].width = ancho
    return _bytes(libro)


# --------------------------------------------------------------------------- PDF (formato oficial)
#
# Estructura basada en los documentos oficiales de Enseñanza Básica y Media:
# Informe de Calificaciones, Certificado Anual de Estudios y Acta de Calificaciones Finales
# y Promoción Escolar (Decreto 67/2018).

NEGRO = colors.black
GRIS_LINEA = colors.HexColor("#808080")
GRIS_FONDO = colors.HexColor("#E7E7E7")

_estilos = getSampleStyleSheet()
E_NORMAL = ParagraphStyle("normal", parent=_estilos["Normal"], fontName="Helvetica", fontSize=9.5, leading=12.5)
E_JUSTO = ParagraphStyle("justo", parent=E_NORMAL, alignment=4, fontSize=10.5, leading=16)
E_CELDA = ParagraphStyle("celda", parent=E_NORMAL, fontSize=8, leading=9.5)
E_CELDA_C = ParagraphStyle("celdac", parent=E_CELDA, alignment=TA_CENTER)
E_TITULO = ParagraphStyle("titulo", parent=E_NORMAL, fontName="Helvetica-Bold", fontSize=13, leading=16,
                          alignment=TA_CENTER, spaceAfter=2)
E_SUB = ParagraphStyle("sub", parent=E_NORMAL, fontSize=9, alignment=TA_CENTER)
E_MINI = ParagraphStyle("mini", parent=E_NORMAL, fontSize=7, leading=8.5, textColor=colors.HexColor("#444444"))
E_FIRMA = ParagraphStyle("firma", parent=E_NORMAL, fontSize=8.5, leading=10.5, alignment=TA_CENTER)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def _fecha_larga(fecha=None):
    fecha = fecha or timezone.localdate()
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _nombre_mayus(est):
    return " ".join(p for p in [est.nombres, est.apellido_paterno, est.apellido_materno] if p).upper()


def _descripcion_nivel(nivel):
    """'5° Básico' -> '5° año de Enseñanza Básica'."""
    nombre = nivel.nombre
    if nivel.ensenanza == "BASICA" and "básico" in nombre.lower():
        return nombre.lower().replace("básico", "").strip() + " año de Enseñanza Básica"
    if nivel.ensenanza == "MEDIA" and "medio" in nombre.lower():
        return nombre.split()[0] + " año de Enseñanza Media"
    if nivel.ensenanza == "PARVULARIA":
        return f"{nombre} (Educación Parvularia)"
    return nombre


def _tipo_ensenanza(nivel):
    return nivel.get_ensenanza_display() if nivel.ensenanza else ""


def _siguiente_nivel(nivel):
    from .models import Nivel
    return Nivel.objects.filter(orden__gt=nivel.orden).order_by("orden").first()


def _membrete(titulo, subtitulo=""):
    """Membrete oficial: República de Chile / Ministerio de Educación + datos del establecimiento."""
    est = Establecimiento.actual()
    izquierda = Paragraph(
        "<b>REPÚBLICA DE CHILE</b><br/>MINISTERIO DE EDUCACIÓN<br/>"
        + (f"REGIÓN DE {est.region.upper()}<br/>" if est.region and not est.region.lower().startswith("regi") else (f"{est.region.upper()}<br/>" if est.region else ""))
        + "<font size=7>Decreto de Evaluación y Promoción N° 67 de 2018</font>", E_MINI)
    datos = [f"<b>{est.nombre.upper()}</b>"]
    if est.rbd:
        datos.append(f"RBD {est.rbd}")
    if est.comuna:
        datos.append(f"Comuna de {est.comuna}")
    derecha = Paragraph("<br/>".join(datos), ParagraphStyle("der", parent=E_MINI, alignment=2))
    t = Table([[izquierda, derecha]], colWidths=["50%", "50%"])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    partes = [t, Spacer(1, 14), Paragraph(titulo.upper(), E_TITULO)]
    if subtitulo:
        partes.append(Paragraph(subtitulo, E_SUB))
    partes.append(Spacer(1, 10))
    return partes


def _tabla_datos(filas, anchos):
    t = Table([[Paragraph(f"<b>{a}</b>", E_CELDA), Paragraph(str(b), E_CELDA), Paragraph(f"<b>{c}</b>", E_CELDA),
                Paragraph(str(d), E_CELDA)] for a, b, c, d in filas], colWidths=anchos)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_LINEA), ("BACKGROUND", (0, 0), (0, -1), GRIS_FONDO),
        ("BACKGROUND", (2, 0), (2, -1), GRIS_FONDO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _estilo_oficial(datos, col_notas_desde=1, filas_encabezado=1, filas_pie=0):
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ("BACKGROUND", (0, 0), (-1, filas_encabezado - 1), GRIS_FONDO),
        ("FONTNAME", (0, 0), (-1, filas_encabezado - 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (col_notas_desde, 0), (-1, -1), "CENTER"),
    ]
    if filas_pie:
        estilo += [("BACKGROUND", (0, -filas_pie), (-1, -1), GRIS_FONDO),
                   ("FONTNAME", (0, -filas_pie), (-1, -1), "Helvetica-Bold")]
    for f, fila in enumerate(datos[filas_encabezado:], start=filas_encabezado):
        for c, valor in enumerate(fila):
            if c >= col_notas_desde and isinstance(valor, str) and _es_nota_roja(valor):
                estilo.append(("TEXTCOLOR", (c, f), (c, f), ROJO))
    return TableStyle(estilo)


def _es_nota_roja(texto):
    try:
        return float(texto.replace(",", ".")) < float(NOTA_APROBACION)
    except ValueError:
        return False


def _firmas(nombres, ancho_total=17 * cm, espacio=55):
    celdas = [[Paragraph("_______________________________<br/>" + n, E_FIRMA) for n in nombres]]
    t = Table(celdas, colWidths=[ancho_total / len(nombres)] * len(nombres))
    return [Spacer(1, espacio), t]


def _asistencia_txt(est):
    return f"{est.porcentaje_asistencia:.1f} %".replace(".", ",") if est.porcentaje_asistencia is not None else "—"


def _construir_pdf(historia, horizontal=False, titulo="Documento"):
    salida = BytesIO()
    tam = landscape(letter) if horizontal else letter
    doc = SimpleDocTemplate(salida, pagesize=tam, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=titulo, creator="Pupitre", author=Establecimiento.actual().nombre)

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc_.leftMargin, 0.8 * cm, f"Emitido el {timezone.localdate():%d-%m-%Y} · Pupitre")
        canvas.drawRightString(tam[0] - doc_.rightMargin, 0.8 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


def _sin_estudiantes(titulo):
    return _membrete(titulo) + [Paragraph("No hay estudiantes.", E_NORMAL)]


def pdf_informe_notas(curso, estudiantes, asignaturas_curso=None):
    """Informe de Calificaciones (parcial o semestral), una página por estudiante."""
    asigs, evaluaciones, resumenes = resumen_curso(curso, asignaturas_curso, estudiantes)
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
    historia = []
    for i, r in enumerate(resumenes):
        if i:
            historia.append(PageBreak())
        e = r.estudiante
        historia += _membrete("Informe de calificaciones", f"Año escolar {curso.anio}")
        historia.append(_tabla_datos([
            ("Estudiante", _nombre_mayus(e), "RUN", e.rut_formateado),
            ("Curso", f"{curso.nombre_corto} · {_tipo_ensenanza(curso.nivel)}", "Profesor(a) jefe", jefe or "—"),
        ], [2.6 * cm, 7 * cm, 2.8 * cm, 4.6 * cm]))
        historia.append(Spacer(1, 10))
        datos = [["Asignatura", "Calificaciones 1er semestre", "Prom.\n1er sem.", "Calificaciones 2do semestre",
                  "Prom.\n2do sem.", "Prom.\nfinal"]]
        for pa in r.asignaturas:
            evs = evaluaciones[pa.asignatura_curso.id]
            notas_sem = []
            for sem in (1, 2):
                partes = []
                for ev in evs:
                    n = pa.notas.get(ev.id)
                    if ev.semestre == sem and n is not None:
                        txt = formato_nota(n)
                        partes.append(f'<font color="#C00000">{txt}</font>' if n < NOTA_APROBACION else txt)
                notas_sem.append(Paragraph("&nbsp;&nbsp;".join(partes) or "", E_CELDA_C))
            final = formato_nota(pa.final) if pa.incide else (f"{concepto(pa.final)}" if pa.final is not None else "")
            nombre = str(pa.asignatura_curso.asignatura) + ("" if pa.incide else " *")
            datos.append([Paragraph(nombre, E_CELDA), notas_sem[0], formato_nota(pa.s1),
                          notas_sem[1], formato_nota(pa.s2), final])
        datos.append(["Promedio general", "", formato_nota(r.promedio_s1), "", formato_nota(r.promedio_s2),
                      formato_nota(r.promedio_general)])
        t = Table(datos, colWidths=[4.2 * cm, 4.4 * cm, 1.4 * cm, 4.4 * cm, 1.4 * cm, 1.4 * cm], repeatRows=1)
        t.setStyle(_estilo_oficial(datos, 1, filas_pie=1))
        historia += [t, Spacer(1, 8)]
        historia.append(_tabla_datos([("Asistencia", _asistencia_txt(e), "Escala", "1,0 a 7,0 · aprobación 4,0")],
                                     [2.6 * cm, 7 * cm, 2.8 * cm, 4.6 * cm]))
        if any(not pa.incide for pa in r.asignaturas):
            historia.append(Paragraph("* No incide en el promedio ni en la promoción; se informa con concepto: "
                                      "MB muy bueno, B bueno, S suficiente, I insuficiente.", E_MINI))
        historia.append(Spacer(1, 6))
        historia.append(Paragraph("Observaciones: ____________________________________________________________"
                                  "______________________________", E_NORMAL))
        historia += _firmas([f"{jefe}<br/>Profesor(a) jefe", "Apoderado(a)"])
    return _construir_pdf(historia or _sin_estudiantes("Informe de calificaciones"), titulo="Informe de calificaciones")


def pdf_informe_final(curso, estudiantes=None):
    """Certificado Anual de Estudios, una página por estudiante."""
    asigs, _, resumenes = resumen_curso(curso, None, estudiantes)
    est = Establecimiento.actual()
    nivel = curso.nivel
    siguiente = _siguiente_nivel(nivel)
    historia = []
    for i, r in enumerate(resumenes):
        if i:
            historia.append(PageBreak())
        e = r.estudiante
        historia += _membrete("Certificado anual de estudios", _tipo_ensenanza(nivel))
        reconocimiento = (f", reconocido oficialmente por el Ministerio de Educación según {est.resolucion_reconocimiento}"
                          if est.resolucion_reconocimiento else ", reconocido oficialmente por el Ministerio de Educación")
        plan = f"Plan de Estudios aprobado por {nivel.decreto_plan_estudios}" if nivel.decreto_plan_estudios \
            else "Plan de Estudios vigente"
        region = f", Región de {est.region}" if est.region else ""
        texto = (
            f"{est.director or '____________________'}, Director(a) del establecimiento educacional "
            f"<b>{est.nombre}</b>, RBD {est.rbd or '______'}, de la comuna de {est.comuna or '______'}{region}"
            f"{reconocimiento}, certifica que <b>{_nombre_mayus(e)}</b>, RUN <b>{e.rut_formateado}</b>, "
            f"cursó el <b>{_descripcion_nivel(nivel)}</b> durante el año escolar <b>{curso.anio}</b>, de acuerdo al "
            f"{plan} y al Reglamento de Evaluación y Promoción Escolar (Decreto N° 67 de 2018), "
            f"obteniendo las siguientes calificaciones finales:"
        )
        historia += [Paragraph(texto, E_JUSTO), Spacer(1, 10)]
        datos = [["Asignatura", "Calificación", "En palabras"]]
        for pa in [p for p in r.asignaturas if p.incide]:
            datos.append([str(pa.asignatura_curso.asignatura), formato_nota(pa.final), nota_en_palabras(pa.final)])
        conceptuales = [p for p in r.asignaturas if not p.incide]
        datos.append(["PROMEDIO GENERAL", formato_nota(r.promedio_general), nota_en_palabras(r.promedio_general)])
        datos.append(["PORCENTAJE DE ASISTENCIA", _asistencia_txt(e), ""])
        t = Table(datos, colWidths=[8 * cm, 3 * cm, 6 * cm], repeatRows=1)
        estilo = _estilo_oficial(datos, 1, filas_pie=2)
        estilo.add("ALIGN", (2, 1), (2, -1), "LEFT")
        t.setStyle(estilo)
        historia += [t, Spacer(1, 8)]
        if conceptuales:
            filas_c = [["Asignaturas y talleres sin incidencia en el promedio", "Concepto", ""]]
            for pa in conceptuales:
                filas_c.append([str(pa.asignatura_curso.asignatura), concepto(pa.final), concepto(pa.final, largo=True)])
            tc = Table(filas_c, colWidths=[8 * cm, 3 * cm, 6 * cm])
            estilo_c = _estilo_oficial(filas_c, 1)
            estilo_c.add("ALIGN", (2, 1), (2, -1), "LEFT")
            tc.setStyle(estilo_c)
            historia += [tc, Spacer(1, 10)]
        if r.situacion.startswith("Promovido"):
            destino = f" a {_descripcion_nivel(siguiente)}" if siguiente else ""
            resultado = f"En consecuencia, el (la) estudiante es <b>PROMOVIDO(A){destino}</b>."
        elif r.situacion.startswith("Reprobado"):
            resultado = f"En consecuencia, el (la) estudiante <b>REPRUEBA</b> el {_descripcion_nivel(nivel)}."
        else:
            resultado = f"Situación final: <b>{r.situacion.upper()}</b>."
        historia += [Paragraph(resultado, E_JUSTO), Spacer(1, 6),
                     Paragraph("Se extiende el presente certificado para los fines que estime conveniente.", E_JUSTO),
                     Spacer(1, 8),
                     Paragraph(f"{est.comuna or '__________'}, {_fecha_larga()}.", ParagraphStyle("fecha", parent=E_JUSTO, alignment=2))]
        historia += _firmas([f"{est.director}<br/>Director(a)<br/>Firma y timbre"], ancho_total=8 * cm, espacio=60)
    return _construir_pdf(historia or _sin_estudiantes("Certificado anual de estudios"),
                          titulo="Certificado anual de estudios")


ABREVIATURAS = {
    "Lenguaje y Comunicación": "Lenguaje", "Lengua y Literatura": "Lengua y Lit.", "Matemática": "Matem.",
    "Historia, Geografía y Cs. Sociales": "Historia", "Ciencias Naturales": "Ciencias", "Inglés": "Inglés",
    "Artes Visuales": "Artes", "Música": "Música", "Educación Física y Salud": "Ed. Física",
    "Tecnología": "Tecnol.", "Orientación": "Orient.", "Religión": "Religión",
}


def _abreviatura(asignatura):
    return asignatura.codigo or ABREVIATURAS.get(asignatura.nombre, asignatura.nombre)


def pdf_acta_final_curso(curso):
    """Acta de Calificaciones Finales y Promoción Escolar (incluye retirados)."""
    estudiantes = list(curso.estudiantes.all())
    del_plan = [ac for ac in curso.asignaturas_curso.select_related("asignatura", "profesor") if ac.asignatura.tipo != "TALLER"]
    asigs, _, resumenes = resumen_curso(curso, del_plan, estudiantes)
    est = Establecimiento.actual()
    nivel = curso.nivel
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
    historia = _membrete("Acta de calificaciones finales y promoción escolar", f"Año escolar {curso.anio}")
    historia.append(_tabla_datos([
        ("Establecimiento", f"{est.nombre} · RBD {est.rbd or '—'}", "Comuna / Región", f"{est.comuna or '—'} / {est.region or '—'}"),
        ("Curso", f"{_descripcion_nivel(nivel)} {curso.letra}", "Tipo de enseñanza", _tipo_ensenanza(nivel) or "—"),
        ("Plan de estudios", nivel.decreto_plan_estudios or "—", "Evaluación y promoción", "Decreto N° 67 de 2018"),
        ("Profesor(a) jefe", jefe or "—", "Reconocimiento oficial", est.resolucion_reconocimiento or "—"),
    ], [3.2 * cm, 8.8 * cm, 3.8 * cm, 8 * cm]))
    historia.append(Spacer(1, 8))
    estilo_h = ParagraphStyle("h", parent=E_CELDA_C, fontSize=6.5, leading=7.5, splitLongWords=0)
    encabezado = ["N°", "RUN", "Nombre del estudiante", "Sexo"] + [
        Paragraph(f"<b>{_abreviatura(a.asignatura)}</b>", estilo_h) for a in asigs] + ["Prom.\ngral.", "%\nasist.", "Sit.\nfinal"]
    datos = [encabezado]
    codigo = {"Promovido(a)": "P", "Reprobado(a)": "R", "Retirado(a)": "Y"}
    conteo = {(c, g): 0 for c in "PRY" for g in "MF"}
    for i, r in enumerate(resumenes, start=1):
        e = r.estudiante
        sit = codigo.get(r.situacion, "—")
        if sit in "PRY" and e.genero in ("M", "F"):
            conteo[(sit, e.genero)] += 1
        nombre = " ".join(p for p in [e.apellido_paterno, e.apellido_materno, e.nombres] if p).upper()
        datos.append([str(i), e.rut_formateado, Paragraph(nombre, E_CELDA), e.genero or ""]
                     + ([formato_nota(p.final) if p.incide else concepto(p.final) for p in r.asignaturas]
                        if sit != "Y" else [""] * len(asigs))
                     + [formato_nota(r.promedio_general) if sit != "Y" else "", _asistencia_txt(e).replace(" %", ""), sit])
    ancho = landscape(letter)[0] - 4 * cm
    fijos = [0.7 * cm, 2.1 * cm, 5.6 * cm, 0.9 * cm]
    finales = [1.1 * cm, 1.1 * cm, 1 * cm]
    ancho_asig = max(1 * cm, (ancho - sum(fijos) - sum(finales)) / max(len(asigs), 1))
    t = Table(datos, colWidths=fijos + [ancho_asig] * len(asigs) + finales, repeatRows=1)
    estilo = _estilo_oficial(datos, 3)
    estilo.add("FONTSIZE", (0, 1), (-1, -1), 7.5)
    t.setStyle(estilo)
    historia += [t, Spacer(1, 10)]
    resumen = [["Resumen", "Hombres", "Mujeres", "Total"]]
    for nombre, c in (("Promovidos (P)", "P"), ("Reprobados (R)", "R"), ("Retirados (Y)", "Y")):
        resumen.append([nombre, conteo[(c, "M")], conteo[(c, "F")], conteo[(c, "M")] + conteo[(c, "F")]])
    tr = Table(resumen, colWidths=[3.5 * cm, 2 * cm, 2 * cm, 2 * cm])
    tr.setStyle(_estilo_oficial(resumen, 1))
    nota = Paragraph("P: promovido(a) · R: reprobado(a) · Y: retirado(a) · —: pendiente (asistencia bajo 85 % o sin notas). Asistencia mínima para la promoción: 85 % "
                     "(Decreto 67/2018, art. 10), salvo autorización del Director(a).", E_MINI)
    historia.append(Table([[tr, nota]], colWidths=[10 * cm, ancho - 10 * cm],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    historia += _firmas([f"{jefe}<br/>Profesor(a) jefe", f"{est.director}<br/>Director(a)<br/>Firma y timbre"],
                        ancho_total=ancho, espacio=45)
    historia.append(Spacer(1, 4))
    historia.append(Paragraph(f"{est.comuna or ''}, {_fecha_larga()}.", ParagraphStyle("f", parent=E_NORMAL, alignment=2)))
    return _construir_pdf(historia, horizontal=True, titulo="Acta de calificaciones finales")
