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

from .calculos import formato_nota, resumen_curso
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
                    + [_xl_nota(p.final) for p in r.asignaturas] + [_xl_nota(r.promedio_general), r.situacion])
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
    titulos = ["RUT", "Apellido paterno", "Apellido materno", "Nombres", "Curso", "Fecha nacimiento",
               "Dirección", "Comuna", "Teléfono", "Email", "Apoderado", "RUT apoderado", "Teléfono apoderado",
               "Contacto emergencia", "Teléfono emergencia", "Activo"]
    _xl_encabezado(hoja, 1, titulos)
    for e in estudiantes.select_related("curso__nivel"):
        hoja.append([
            e.rut_formateado, e.apellido_paterno, e.apellido_materno, e.nombres,
            e.curso.nombre_corto if e.curso else "", e.fecha_nacimiento.strftime("%d-%m-%Y") if e.fecha_nacimiento else "",
            e.direccion, e.comuna, e.telefono, e.email, e.apoderado_nombre, e.apoderado_rut,
            e.apoderado_telefono, e.contacto_emergencia, e.telefono_emergencia, "Sí" if e.activo else "No",
        ])
    for col in "ABCDEFGHIJKLMNOP":
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


# --------------------------------------------------------------------------- PDF

_estilos = getSampleStyleSheet()
E_TITULO = ParagraphStyle("titulo", parent=_estilos["Title"], fontSize=15, textColor=AZUL, spaceAfter=4)
E_SUB = ParagraphStyle("sub", parent=_estilos["Normal"], fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
E_NORMAL = ParagraphStyle("normal", parent=_estilos["Normal"], fontSize=9, leading=11)
E_CELDA = ParagraphStyle("celda", parent=E_NORMAL, fontSize=8, leading=10)
E_FIRMA = ParagraphStyle("firma", parent=E_NORMAL, alignment=TA_CENTER)


def _encabezado_pdf(titulo, subtitulo=""):
    est = Establecimiento.actual()
    datos = " · ".join(x for x in [f"RBD {est.rbd}" if est.rbd else "", est.direccion, est.comuna] if x)
    partes = [Paragraph(f"<b>{est.nombre}</b>", ParagraphStyle("est", parent=E_NORMAL, fontSize=11, leading=14, alignment=TA_CENTER))]
    if datos:
        partes.append(Paragraph(datos, E_SUB))
    partes += [Spacer(1, 8), Paragraph(titulo, E_TITULO)]
    if subtitulo:
        partes.append(Paragraph(subtitulo, E_SUB))
    partes.append(Spacer(1, 10))
    return partes


def _ficha_estudiante(est, curso):
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else "—"
    datos = [
        ["Estudiante:", est.nombre_completo, "RUT:", est.rut_formateado],
        ["Curso:", str(curso), "Profesor(a) jefe:", jefe],
    ]
    t = Table(datos, colWidths=[2.6 * cm, 7.4 * cm, 3.2 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, 10)]


def _estilo_tabla(datos, col_notas_desde=1, encabezado_filas=1):
    estilo = [
        ("BACKGROUND", (0, 0), (-1, encabezado_filas - 1), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, encabezado_filas - 1), colors.white),
        ("FONTNAME", (0, 0), (-1, encabezado_filas - 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (col_notas_desde, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, encabezado_filas), (-1, -1), [colors.white, GRIS]),
    ]
    for f, fila in enumerate(datos[encabezado_filas:], start=encabezado_filas):
        for c, valor in enumerate(fila):
            if c >= col_notas_desde and isinstance(valor, str) and _es_nota_roja(valor):
                estilo.append(("TEXTCOLOR", (c, f), (c, f), ROJO))
    return TableStyle(estilo)


def _es_nota_roja(texto):
    try:
        return float(texto.replace(",", ".")) < float(NOTA_APROBACION)
    except ValueError:
        return False


def _firmas(nombres):
    celdas = [[Paragraph("_________________________<br/>" + n, E_FIRMA) for n in nombres]]
    return [Spacer(1, 50), Table(celdas, colWidths=[18 * cm / len(nombres)] * len(nombres))]


def _construir_pdf(historia, horizontal=False):
    salida = BytesIO()
    tam = landscape(letter) if horizontal else letter
    doc = SimpleDocTemplate(salida, pagesize=tam, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title="Informe de calificaciones", creator="Pupitre", author=Establecimiento.actual().nombre)

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc_.leftMargin, 0.8 * cm, f"Emitido el {timezone.localdate():%d-%m-%Y}")
        canvas.drawRightString(tam[0] - doc_.rightMargin, 0.8 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


def pdf_informe_notas(curso, estudiantes, asignaturas_curso=None):
    """Informe de notas parcial (todas las notas por semestre), una página por estudiante."""
    asigs, evaluaciones, resumenes = resumen_curso(curso, asignaturas_curso, estudiantes)
    historia = []
    for i, r in enumerate(resumenes):
        if i:
            historia.append(PageBreak())
        historia += _encabezado_pdf("Informe de calificaciones", f"Año académico {curso.anio}")
        historia += _ficha_estudiante(r.estudiante, curso)
        datos = [["Asignatura", "Notas 1er semestre", "Prom. S1", "Notas 2do semestre", "Prom. S2", "Prom. final"]]
        for pa in r.asignaturas:
            evs = evaluaciones[pa.asignatura_curso.id]
            notas_sem = []
            for s in (1, 2):
                partes = []
                for e in evs:
                    n = pa.notas.get(e.id)
                    if e.semestre == s and n is not None:
                        txt = formato_nota(n)
                        partes.append(f'<font color="#C00000">{txt}</font>' if n < NOTA_APROBACION else txt)
                notas_sem.append(Paragraph("&nbsp;&nbsp;".join(partes) or "—", E_CELDA))
            datos.append([Paragraph(str(pa.asignatura_curso.asignatura), E_CELDA), notas_sem[0],
                          formato_nota(pa.s1), notas_sem[1], formato_nota(pa.s2), formato_nota(pa.final)])
        datos.append(["Promedio general", "", formato_nota(r.promedio_s1), "", formato_nota(r.promedio_s2),
                      formato_nota(r.promedio_general)])
        t = Table(datos, colWidths=[4 * cm, 4.6 * cm, 1.7 * cm, 4.6 * cm, 1.7 * cm, 1.8 * cm], repeatRows=1)
        estilo = _estilo_tabla(datos, col_notas_desde=1)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        historia.append(t)
        historia.append(Spacer(1, 6))
        historia.append(Paragraph("Notas en rojo: calificación insuficiente (bajo 4,0).", E_SUB))
        jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else "Profesor(a) jefe"
        historia += _firmas([f"{jefe}<br/>Profesor(a) jefe"])
    if not historia:
        historia = _encabezado_pdf("Informe de calificaciones") + [Paragraph("No hay estudiantes.", E_NORMAL)]
    return _construir_pdf(historia)


def pdf_informe_final(curso, estudiantes=None):
    """Informe final (certificado anual) por estudiante, una página por estudiante."""
    asigs, _, resumenes = resumen_curso(curso, None, estudiantes)
    est = Establecimiento.actual()
    historia = []
    for i, r in enumerate(resumenes):
        if i:
            historia.append(PageBreak())
        historia += _encabezado_pdf("Informe final de calificaciones", f"Año académico {curso.anio}")
        historia += _ficha_estudiante(r.estudiante, curso)
        datos = [["Asignatura", "1er semestre", "2do semestre", "Promedio final", "Situación"]]
        for pa in r.asignaturas:
            situacion = "" if pa.final is None else ("Aprobada" if pa.aprobada else "Reprobada")
            datos.append([str(pa.asignatura_curso.asignatura), formato_nota(pa.s1), formato_nota(pa.s2),
                          formato_nota(pa.final), situacion])
        datos.append(["Promedio general", formato_nota(r.promedio_s1), formato_nota(r.promedio_s2),
                      formato_nota(r.promedio_general), ""])
        t = Table(datos, colWidths=[6 * cm, 2.8 * cm, 2.8 * cm, 3 * cm, 3.4 * cm], repeatRows=1)
        estilo = _estilo_tabla(datos, col_notas_desde=1)
        estilo.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        t.setStyle(estilo)
        historia.append(t)
        historia.append(Spacer(1, 14))
        color = "#1F4E79" if r.situacion.startswith("Promovido") else "#C00000"
        historia.append(Paragraph(
            f'Situación final: <font color="{color}"><b>{r.situacion}</b></font>',
            ParagraphStyle("sit", parent=E_NORMAL, fontSize=11)))
        historia.append(Spacer(1, 4))
        historia.append(Paragraph(
            "La situación final considera solo el rendimiento académico (Decreto 67/2018); "
            "la asistencia debe verificarse por separado.", E_SUB))
        jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
        historia += _firmas([f"{jefe}<br/>Profesor(a) jefe", f"{est.director}<br/>Director(a)"])
    if not historia:
        historia = _encabezado_pdf("Informe final de calificaciones") + [Paragraph("No hay estudiantes.", E_NORMAL)]
    return _construir_pdf(historia)


def pdf_acta_final_curso(curso):
    """Resumen final del curso en una tabla (hoja horizontal)."""
    asigs, _, resumenes = resumen_curso(curso)
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else "—"
    historia = _encabezado_pdf(f"Acta de calificaciones finales – {curso}", f"Profesor(a) jefe: {jefe}")
    encabezado = ["N°", "RUT", "Estudiante"] + [
        Paragraph(f"<b>{a.asignatura}</b>", ParagraphStyle("h", parent=E_CELDA, textColor=colors.white,
                                                            alignment=TA_CENTER, fontSize=7))
        for a in asigs
    ] + ["Prom.", "Situación"]
    datos = [encabezado]
    for i, r in enumerate(resumenes, start=1):
        datos.append([str(i), r.estudiante.rut_formateado, Paragraph(r.estudiante.nombre_completo, E_CELDA)]
                     + [formato_nota(p.final) for p in r.asignaturas]
                     + [formato_nota(r.promedio_general), r.situacion])
    ancho_disponible = landscape(letter)[0] - 3.2 * cm
    fijos = [0.8 * cm, 2.2 * cm, 5.2 * cm]
    finales = [1.3 * cm, 2.6 * cm]
    ancho_asig = max(1.1 * cm, (ancho_disponible - sum(fijos) - sum(finales)) / max(len(asigs), 1))
    t = Table(datos, colWidths=fijos + [ancho_asig] * len(asigs) + finales, repeatRows=1)
    t.setStyle(_estilo_tabla(datos, col_notas_desde=3))
    historia.append(t)
    est = Establecimiento.actual()
    historia += _firmas([f"{jefe}<br/>Profesor(a) jefe", f"{est.jefe_utp}<br/>Jefe(a) de UTP",
                         f"{est.director}<br/>Director(a)"])
    return _construir_pdf(historia, horizontal=True)
