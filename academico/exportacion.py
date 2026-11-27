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
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from django.utils.html import escape

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
    if est.pie_documentos:
        hoja["A4"] = est.pie_documentos
        hoja["A4"].font = Font(italic=True, size=9, color="666666")
        hoja.oddFooter.center.text = est.pie_documentos
    hoja.pupitre_con_logo = True  # el logo se agrega al final, cuando se conoce el ancho de la tabla


def _xl_pintar_notas(hoja, fila_ini, col_ini):
    for fila in hoja.iter_rows(min_row=fila_ini, min_col=col_ini):
        for c in fila:
            if isinstance(c.value, (int, float)):
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="center")
                if c.value < float(NOTA_APROBACION):
                    c.font = _ROJO_XL


def _xl_logo(libro):
    """Logo institucional en la esquina superior derecha de las planillas (no en documentos oficiales)."""
    est = Establecimiento.actual()
    if not est.logo:
        return
    from openpyxl.drawing.image import Image as XLImagen
    from openpyxl.utils import get_column_letter
    from PIL import Image

    for hoja in libro.worksheets:
        if not getattr(hoja, "pupitre_con_logo", False):
            continue
        img = Image.open(BytesIO(bytes(est.logo)))
        alto = 50
        ancho = max(1, int(img.width * alto / img.height))
        xl = XLImagen(BytesIO(bytes(est.logo)))
        xl.height, xl.width = alto, ancho
        # a la derecha del título: se busca la primera columna libre después del texto más largo
        largo = max(len(str(hoja[f"A{f}"].value or "")) * (1.35 if f <= 2 else 1.0) for f in (1, 2, 3, 4))
        acumulado, columna = 0, 1
        while acumulado < largo and columna < 40:
            acumulado += hoja.column_dimensions[get_column_letter(columna)].width or 8.43
            columna += 1
        hoja.add_image(xl, f"{get_column_letter(columna)}1")


def _bytes(libro):
    _xl_logo(libro)
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
    resumenes = [r for r in resumenes if r.asignaturas[0].aplica]
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
                    + [(concepto(p.final) if p.con_concepto else _xl_nota(p.final)) if p.aplica else None
                       for p in r.asignaturas]
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
                             "Descripción", "Medida", "Registrada por", "Derivada a Convivencia"])
    for a in anotaciones.select_related("estudiante__curso__nivel", "asignatura", "autor"):
        hoja.append([
            a.fecha.strftime("%d-%m-%Y"), a.estudiante.rut_formateado, a.estudiante.nombre_completo,
            a.estudiante.curso.nombre_corto if a.estudiante.curso else "", a.get_tipo_display(),
            a.get_gravedad_display(), str(a.asignatura or ""), a.descripcion, a.medida,
            a.autor.get_full_name() if a.autor else "", "Sí" if a.derivada else "",
        ])
    for col, ancho in zip("ABCDEFGHIJK", (12, 14, 32, 14, 12, 12, 18, 60, 40, 24, 12)):
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
        primero = nombre.split()[0]
        primero = {"I": "1°", "II": "2°", "III": "3°", "IV": "4°"}.get(primero.upper(), primero)
        return primero + " año de Enseñanza Media"
    if nivel.ensenanza == "PARVULARIA":
        return f"{nombre} (Educación Parvularia)"
    return nombre


def _tipo_ensenanza(nivel, curso=None):
    if curso is not None and nivel.ensenanza == "MEDIA" and curso.modalidad:
        if curso.modalidad == "TP":
            texto = "Enseñanza Media Técnico-Profesional"
            if curso.especialidad:
                texto += f" · Especialidad {curso.especialidad}"
                if curso.mencion:
                    texto += f", mención {curso.mencion}"
            return texto
        return "Enseñanza Media Científico-Humanista"
    return nivel.get_ensenanza_display() if nivel.ensenanza else ""


def _siguiente_nivel(nivel):
    from .models import Nivel
    return Nivel.objects.filter(orden__gt=nivel.orden).order_by("orden").first()


def _membrete(titulo, subtitulo="", decreto=True):
    """Membrete oficial: República de Chile / Ministerio de Educación + datos del establecimiento."""
    est = Establecimiento.actual()
    izquierda = Paragraph(
        "<b>REPÚBLICA DE CHILE</b><br/>MINISTERIO DE EDUCACIÓN<br/>"
        + (f"REGIÓN DE {est.region.upper()}<br/>" if est.region and not est.region.lower().startswith("regi") else (f"{est.region.upper()}<br/>" if est.region else ""))
        + ("<font size=7>Decreto de Evaluación y Promoción N° 67 de 2018</font>" if decreto else ""), E_MINI)
    datos = [f"<b>{est.nombre.upper()}</b>"]
    if est.rbd:
        datos.append(f"RBD {est.rbd}")
    if est.comuna:
        datos.append(f"Comuna de {est.comuna}")
    derecha = Paragraph("<br/>".join(datos), ParagraphStyle("der", parent=E_MINI, alignment=2))
    if not decreto and est.logo:  # documentos internos: con logo institucional
        from reportlab.platypus import Image as PDFImagen
        from PIL import Image

        img = Image.open(BytesIO(bytes(est.logo)))
        alto = 1.6 * cm
        logo = PDFImagen(BytesIO(bytes(est.logo)), width=alto * img.width / img.height, height=alto)
        izquierda = Table([[logo, izquierda]], colWidths=[alto * img.width / img.height + 0.3 * cm, None])
        izquierda.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
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


def _construir_pdf(historia, horizontal=False, titulo="Documento", interno=False):
    salida = BytesIO()
    tam = landscape(letter) if horizontal else letter
    doc = SimpleDocTemplate(salida, pagesize=tam, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=titulo, creator="Pupitre", author=Establecimiento.actual().nombre)

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        texto = f"Emitido el {timezone.localdate():%d-%m-%Y} · Pupitre"
        pie_extra = Establecimiento.actual().pie_documentos if interno else ""
        if pie_extra:
            texto = f"{pie_extra} · {texto}"
        canvas.drawString(doc_.leftMargin, 0.8 * cm, texto)
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
            ("Curso", f"{curso.nombre_corto} · {_tipo_ensenanza(curso.nivel, curso)}", "Profesor(a) jefe", jefe or "—"),
        ], [2.6 * cm, 7 * cm, 2.8 * cm, 4.6 * cm]))
        historia.append(Spacer(1, 10))
        datos = [["Asignatura", "Calificaciones 1er semestre", "Prom.\n1er sem.", "Calificaciones 2do semestre",
                  "Prom.\n2do sem.", "Prom.\nfinal"]]
        for pa in [p for p in r.asignaturas if p.aplica]:
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
            final = concepto(pa.final) if pa.con_concepto else formato_nota(pa.final)
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
        if any(pa.aplica and not pa.incide for pa in r.asignaturas):
            historia.append(Paragraph("* No incide en el promedio general ni en la promoción (Decreto 67/2018).", E_MINI))
        if any(pa.aplica and pa.con_concepto for pa in r.asignaturas):
            historia.append(Paragraph("Conceptos: MB muy bueno, B bueno, S suficiente, I insuficiente.", E_MINI))
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
        historia += _membrete("Certificado anual de estudios", _tipo_ensenanza(nivel, curso))
        reconocimiento = (f", reconocido oficialmente por el Ministerio de Educación según {est.resolucion_reconocimiento}"
                          if est.resolucion_reconocimiento else ", reconocido oficialmente por el Ministerio de Educación")
        plan = f"Plan de Estudios aprobado por {curso.decreto_plan}" if curso.decreto_plan \
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
        conceptuales = [p for p in r.asignaturas if p.aplica and not p.incide]
        datos.append(["PROMEDIO GENERAL", formato_nota(r.promedio_general), nota_en_palabras(r.promedio_general)])
        datos.append(["PORCENTAJE DE ASISTENCIA", _asistencia_txt(e), ""])
        t = Table(datos, colWidths=[8 * cm, 3 * cm, 6 * cm], repeatRows=1)
        estilo = _estilo_oficial(datos, 1, filas_pie=2)
        estilo.add("ALIGN", (2, 1), (2, -1), "LEFT")
        t.setStyle(estilo)
        historia += [t, Spacer(1, 8)]
        if conceptuales:
            filas_c = [["Sin incidencia en el promedio ni en la promoción", "Calificación", "En palabras"]]
            for pa in conceptuales:
                if pa.con_concepto:
                    filas_c.append([str(pa.asignatura_curso.asignatura), concepto(pa.final), concepto(pa.final, largo=True)])
                else:
                    filas_c.append([str(pa.asignatura_curso.asignatura), formato_nota(pa.final), nota_en_palabras(pa.final)])
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
    "Religión Católica": "Rel. Católica", "Religión Evangélica": "Rel. Evang.",
    "Educación Ciudadana": "Ed. Ciud.", "Ciencias para la Ciudadanía": "Cs. Ciud.", "Filosofía": "Filosofía",
    "Taller de Arte y Folclor": "T. Arte Folclor", "Taller de Robótica": "T. Robótica", "Taller de Deportes": "T. Deportes",
}


def _celda_acta(p):
    if not p.aplica:
        return ""
    return concepto(p.final) if p.con_concepto else formato_nota(p.final)


def _abreviatura(asignatura):
    nombre = asignatura.nombre
    if asignatura.codigo:
        return asignatura.codigo
    if nombre in ABREVIATURAS:
        return ABREVIATURAS[nombre]
    if nombre.lower().startswith("taller de "):
        return "T. " + nombre[10:]
    if len(nombre) > 16:  # módulos TP y electivos: iniciales de las palabras importantes
        menores = {"de", "del", "la", "las", "los", "el", "y", "e", "para", "en", "a", "con"}
        palabras = [w for w in nombre.replace(",", "").split() if w.lower() not in menores]
        return " ".join(w[:4] + ("." if len(w) > 4 else "") for w in palabras[:4])
    return nombre


def pdf_acta_final_curso(curso):
    """Acta de Calificaciones Finales y Promoción Escolar (incluye retirados)."""
    estudiantes = list(curso.estudiantes.all())
    del_plan = [ac for ac in curso.asignaturas_curso.select_related("asignatura", "profesor")
                if ac.asignatura.tipo != "TALLER" or ac.asignatura.incide_en_promedio]  # talleres con nota que cuenta
    asigs, _, resumenes = resumen_curso(curso, del_plan, estudiantes)
    est = Establecimiento.actual()
    nivel = curso.nivel
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
    historia = _membrete("Acta de calificaciones finales y promoción escolar", f"Año escolar {curso.anio}")
    historia.append(_tabla_datos([
        ("Establecimiento", f"{est.nombre} · RBD {est.rbd or '—'}", "Comuna / Región", f"{est.comuna or '—'} / {est.region or '—'}"),
        ("Curso", f"{_descripcion_nivel(nivel)} {curso.letra}", "Tipo de enseñanza", _tipo_ensenanza(nivel, curso) or "—"),
        ("Plan de estudios", curso.decreto_plan or "—", "Evaluación y promoción", "Decreto N° 67 de 2018"),
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
                     + ([_celda_acta(p) for p in r.asignaturas]
                        if sit != "Y" else [""] * len(asigs))
                     + [formato_nota(r.promedio_general) if sit != "Y" else "", _asistencia_txt(e).replace(" %", ""), sit])
    ancho = landscape(letter)[0] - 4 * cm
    muchas = len(asigs) > 12  # Media TP/HC: formación general + módulos o electivos
    fijos = [0.6 * cm, 1.9 * cm, 4.2 * cm if muchas else 5.6 * cm, 0.8 * cm]
    finales = [1 * cm, 1 * cm, 0.9 * cm]
    ancho_asig = max(0.75 * cm, (ancho - sum(fijos) - sum(finales)) / max(len(asigs), 1))
    t = Table(datos, colWidths=fijos + [ancho_asig] * len(asigs) + finales, repeatRows=1)
    estilo = _estilo_oficial(datos, 3)
    estilo.add("FONTSIZE", (0, 1), (-1, -1), 6.8 if muchas else 7.5)
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


# --------------------------------------------------------------------------- Registro de entrevista

def _texto(valor):
    return escape(valor or "").replace("\n", "<br/>")


def _seccion(titulo, contenido, lineas_vacias=4):
    """Recuadro con título; si no hay contenido (formato en blanco) deja líneas para escribir a mano."""
    encabezado = Paragraph(f"<b>{titulo}</b>", E_CELDA)
    if contenido is None:
        cuerpo = [[""] for _ in range(lineas_vacias)]
        t = Table([[encabezado]] + cuerpo, colWidths=[17 * cm], rowHeights=[None] + [0.75 * cm] * lineas_vacias)
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRIS_LINEA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_FONDO),
                               ("LINEBELOW", (0, 1), (-1, -2), 0.3, GRIS_LINEA)]))
    else:
        t = Table([[encabezado], [Paragraph(_texto(contenido) or "—", E_NORMAL)]], colWidths=[17 * cm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRIS_LINEA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_FONDO),
                               ("TOPPADDING", (0, 1), (-1, 1), 5), ("BOTTOMPADDING", (0, 1), (-1, 1), 7)]))
    return [KeepTogether([t]), Spacer(1, 7)]


def pdf_entrevista(estudiante, entrevista=None):
    """Registro de entrevista. Sin `entrevista` genera el formato en blanco para completar a mano."""
    from .models import Entrevista, OpcionCatalogo

    e = entrevista
    blanco = e is None
    est = Establecimiento.actual()
    curso = estudiante.curso
    jefe = curso.profesor_jefe.get_full_name() if curso and curso.profesor_jefe else ""
    linea = "_" * 28
    if blanco:
        tipo = "   ".join(f"(  ) {t}" for _, t in Entrevista.Tipo.choices)
        historia = _membrete("Registro de entrevista", "Convivencia escolar · Documento confidencial", decreto=False)
    else:
        historia = _membrete("Registro de entrevista", f"{e.get_tipo_display()} · Documento confidencial", decreto=False)
    filas = [
        ("Estudiante", escape(estudiante.nombre_completo), "RUN", estudiante.rut_formateado),
        ("Curso", escape(curso.nombre_corto) if curso else "—", "Profesor(a) jefe", escape(jefe) or "—"),
    ]
    if blanco:
        filas += [("Fecha", "____ / ____ / ________", "Hora", "____ : ____"),
                  ("Persona entrevistada", linea, "Parentesco", linea),
                  ("RUT entrevistado(a)", linea, "Entrevistador(a)", linea),
                  ("Otros asistentes", linea, "Protocolo", linea)]
    else:
        entrevistador = e.entrevistador.get_full_name() if e.entrevistador else ""
        filas += [("Fecha", f"{e.fecha:%d-%m-%Y}", "Hora", e.hora.strftime("%H:%M") if e.hora else "—"),
                  ("Persona entrevistada", escape(e.entrevistado) or "—", "Parentesco", escape(e.parentesco) or "—"),
                  ("RUT entrevistado(a)", e.rut_entrevistado or "—", "Entrevistador(a)", escape(entrevistador) or "—"),
                  ("Otros asistentes", escape(e.otros_asistentes) or "—", "Protocolo",
                   e.get_protocolo_display() if e.protocolo else "No aplica")]
    historia.append(_tabla_datos(filas, [3.4 * cm, 5.4 * cm, 3 * cm, 5.2 * cm]))
    historia.append(Spacer(1, 8))
    if blanco:
        historia.append(Paragraph(f"<b>Tipo de entrevista:</b> {tipo}", E_CELDA))
        historia.append(Spacer(1, 4))
        protocolos = " · ".join(o.nombre for o in OpcionCatalogo.objects.filter(tipo="PROTOCOLO", activo=True))
        historia.append(Paragraph(f"<b>Protocolos del Reglamento Interno:</b> {protocolos}.", E_MINI))
        historia.append(Spacer(1, 8))
    elif e.anotacion:
        a = e.anotacion
        historia += _seccion(f"Anotación relacionada ({a.fecha:%d-%m-%Y}, {a.get_tipo_display()}"
                             f"{' ' + a.get_gravedad_display() if a.gravedad else ''})", a.descripcion)

    def campo(nombre):
        return None if blanco else getattr(e, nombre)

    historia += _seccion("1. Motivo de la entrevista", campo("motivo"), 3)
    historia += _seccion("2. Desarrollo / relato de los hechos", campo("desarrollo"), 8)
    historia += _seccion("3. Acuerdos", campo("acuerdos"), 3)
    historia += _seccion("4. Compromisos del apoderado(a)", campo("compromisos_apoderado"), 3)
    historia += _seccion("5. Compromisos del estudiante", campo("compromisos_estudiante"), 3)
    historia += _seccion("6. Compromisos del establecimiento", campo("compromisos_establecimiento"), 3)
    historia += _seccion("7. Derivaciones (red externa, OLN, Tribunal de Familia, Fiscalía, CESFAM, otras)",
                         campo("derivaciones"), 2)
    seguimiento = ("____ / ____ / ________" if blanco
                   else (f"{e.fecha_seguimiento:%d-%m-%Y}" if e.fecha_seguimiento else "Sin fecha definida"))
    historia.append(Paragraph(f"<b>Fecha de seguimiento:</b> {seguimiento}", E_NORMAL))
    historia.append(Spacer(1, 6))
    historia.append(Paragraph(
        "Documento confidencial. Contiene datos sensibles del estudiante y su familia (Ley N° 19.628 sobre protección "
        "de la vida privada y Ley N° 21.430 sobre garantías de la niñez). Uso exclusivo del establecimiento. "
        "Los participantes declaran haber leído el presente registro.", E_MINI))
    entrevistado = "" if blanco else (escape(e.entrevistado) + "<br/>" if e.entrevistado else "")
    entrevistador = "" if blanco or not e.entrevistador else escape(e.entrevistador.get_full_name()) + "<br/>"
    historia += _firmas([f"{entrevistado}Persona entrevistada", f"{entrevistador}Entrevistador(a)",
                         "Encargado(a) de Convivencia Escolar"], espacio=40)
    historia.append(Spacer(1, 4))
    historia.append(Paragraph(f"{escape(est.comuna or '')}, {'____ de ______________ de ________' if blanco else _fecha_larga(e.fecha)}.",
                              ParagraphStyle("f", parent=E_NORMAL, alignment=2)))
    return _construir_pdf(historia, titulo="Registro de entrevista", interno=True)


# --------------------------------------------------------------------------- Libro de clases

def _firma_txt(clase):
    if clase.firmada:
        quien = clase.firmada_por.get_full_name() if clase.firmada_por else ""
        return f"{escape(quien)}<br/><font size=6>Firma electrónica {timezone.localtime(clase.firmada_en):%d-%m-%Y %H:%M}</font>"
    return "<font color='#C00000'>Sin firma</font>"


def _corto(texto, maximo=420):
    texto = (texto or "").strip()
    return escape(texto if len(texto) <= maximo else texto[:maximo].rsplit(" ", 1)[0] + "…").replace("\n", "<br/>")


def pdf_leccionario(ac, clases):
    """Leccionario de una asignatura: registro clase a clase con asistencia y firma del docente."""
    curso = ac.curso
    historia = _membrete("Libro de clases · Leccionario", f"{escape(ac.asignatura.nombre)} · {escape(curso.nombre_corto)} · Año {curso.anio}",
                         decreto=False)
    profesor = ac.profesor.get_full_name() if ac.profesor else "Sin asignar"
    realizadas = [c for c in clases if c.asistencia_registrada]
    historia.append(_tabla_datos([
        ("Asignatura", escape(ac.asignatura.nombre), "Curso", escape(curso.nombre_corto)),
        ("Profesor(a)", escape(profesor), "Horas semanales", f"{ac.horas_semanales:g}" if ac.horas_semanales else "—"),
        ("Clases registradas", f"{len(realizadas)} ({sum(c.bloques for c in realizadas)} horas pedagógicas)",
         "Clases firmadas", str(sum(1 for c in clases if c.firmada))),
    ], [3.4 * cm, 8.5 * cm, 3.4 * cm, 8.6 * cm]))
    historia.append(Spacer(1, 8))
    enc = ["N°", "Fecha", "Hrs", "Unidad y objetivo de aprendizaje", "Contenidos y actividades", "Aus.",
           "Evaluación", "Firma docente"]
    datos = [[Paragraph(f"<b>{t}</b>", E_CELDA_C) for t in enc]]
    for i, c in enumerate(clases, 1):
        oa = (f"<b>{escape(c.unidad)}</b><br/>" if c.unidad else "") + _corto(c.objetivo, 260)
        act = _corto(c.actividades)
        if c.observaciones:
            act += f"<br/><i>Obs.: {_corto(c.observaciones, 160)}</i>"
        if c.visado_utp:
            act += f"<br/><font color='#1F4E79'><i>UTP: {_corto(c.visado_utp, 160)}</i></font>"
        datos.append([
            Paragraph(str(i), E_CELDA_C),
            Paragraph(f"{c.fecha:%d-%m-%y}" + (f"<br/>{c.hora_inicio:%H:%M}" if c.hora_inicio else ""), E_CELDA_C),
            Paragraph(str(c.bloques), E_CELDA_C), Paragraph(oa, E_CELDA), Paragraph(act or "—", E_CELDA),
            Paragraph(str(c.ausentes) if c.asistencia_registrada else "—", E_CELDA_C),
            Paragraph(escape(c.evaluacion.nombre) if c.evaluacion else "", E_CELDA),
            Paragraph(_firma_txt(c), E_CELDA_C),
        ])
    if len(datos) == 1:
        datos.append([Paragraph("Aún no hay clases registradas.", E_CELDA)] + [""] * 7)
    t = Table(datos, colWidths=[0.8 * cm, 1.8 * cm, 0.9 * cm, 6.2 * cm, 7.4 * cm, 1.5 * cm, 2.3 * cm, 3 * cm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_LINEA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_FONDO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    historia.append(t)
    historia += _firmas([f"{escape(profesor)}<br/>Profesor(a) de asignatura", "Jefe(a) de UTP"], ancho_total=23.9 * cm,
                        espacio=40)
    return _construir_pdf(historia, horizontal=True, titulo="Leccionario", interno=True)


def pdf_asistencia_mes(curso, datos, mes_txt):
    """Registro mensual de asistencia diaria del curso, más las clases realizadas y su firma."""
    historia = _membrete("Libro de clases · Registro de asistencia",
                         f"{escape(curso.nombre_corto)} · {mes_txt.capitalize()}", decreto=False)
    dias = datos["dias"]
    simbolo = {"P": "•", "A": "A", "T": "T", "R": "R", "": ""}
    enc = ["N°", "Estudiante"] + [f"{d.day}" for d in dias] + ["Aus.", "Atr.", "%"]
    filas = [[Paragraph(f"<b>{t}</b>", E_CELDA_C) for t in enc]]
    rojas = []
    for i, f in enumerate(datos["filas"], 1):
        fila = [str(i), Paragraph(escape(f["est"].nombre_completo), E_CELDA)]
        for j, c in enumerate(f["celdas"]):
            fila.append(simbolo.get(c, c))
            if c == "A":
                rojas.append((2 + j, i))
        pct = f"{f['pct']:.1f}".replace(".", ",") if f["pct"] is not None else "—"
        fila += [str(f["ausencias"]), str(f["atrasos"]), pct]
        filas.append(fila)
    ancho_util = 23.9 * cm
    fijo = 0.7 * cm + 5.6 * cm + 3 * 1.1 * cm
    ancho_dia = (ancho_util - fijo) / len(dias) if dias else 1 * cm
    anchos = [0.7 * cm, 5.6 * cm] + [min(ancho_dia, 1 * cm)] * len(dias) + [1.1 * cm] * 3
    t = Table(filas, colWidths=anchos, repeatRows=1)
    estilo = [("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_FONDO),
              ("FONTSIZE", (0, 1), (-1, -1), 7.5), ("ALIGN", (2, 1), (-1, -1), "CENTER"),
              ("ALIGN", (0, 1), (0, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    estilo += [("TEXTCOLOR", celda, celda, ROJO) for celda in rojas]
    t.setStyle(TableStyle(estilo))
    historia.append(t)
    historia.append(Spacer(1, 4))
    historia.append(Paragraph("• Presente · A Ausente · T Atrasado(a) · R Retirado(a) antes del término. "
                              "La asistencia diaria corresponde a la primera clase registrada de cada día.", E_MINI))
    if datos["clases"]:
        historia.append(Spacer(1, 10))
        historia.append(Paragraph("<b>Clases del mes</b>", E_NORMAL))
        historia.append(Spacer(1, 4))
        cl = [[Paragraph(f"<b>{t}</b>", E_CELDA_C) for t in ["Fecha", "Asignatura", "Hrs", "Objetivo de aprendizaje", "Firma docente"]]]
        for c in datos["clases"]:
            cl.append([Paragraph(f"{c.fecha:%d-%m}", E_CELDA_C), Paragraph(escape(c.asignatura_curso.asignatura.nombre), E_CELDA),
                       Paragraph(str(c.bloques), E_CELDA_C), Paragraph(_corto(c.objetivo, 200), E_CELDA),
                       Paragraph(_firma_txt(c), E_CELDA_C)])
        tc = Table(cl, colWidths=[1.5 * cm, 4.5 * cm, 1 * cm, 13.4 * cm, 3.5 * cm], repeatRows=1)
        tc.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA), ("BACKGROUND", (0, 0), (-1, 0), GRIS_FONDO),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        historia.append(tc)
    jefe = curso.profesor_jefe.get_full_name() if curso.profesor_jefe else ""
    historia += _firmas([f"{escape(jefe)}<br/>Profesor(a) jefe", "Inspectoría General"], ancho_total=23.9 * cm, espacio=40)
    return _construir_pdf(historia, horizontal=True, titulo="Registro de asistencia", interno=True)
