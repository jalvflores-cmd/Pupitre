"""Revisión del PME: coherencia con el PEI, vínculo con el Marco para la Buena Dirección y el Liderazgo Escolar
(MBDLE, Mineduc 2015) y lectura del archivo del PME descargado de Comunidad Escolar.

Todo se calcula con reglas transparentes (coincidencia de palabras clave), sin IA. La revisión con IA es opcional.
Los contenidos del MBDLE están resumidos y deben contrastarse con el documento oficial (Mineduc / CPEIP, 2015).
"""
import re
import unicodedata
from io import BytesIO

NOTA_MBDLE = ("Dimensiones y prácticas resumidas del Marco para la Buena Dirección y el Liderazgo Escolar (Mineduc, "
              "2015). Es una síntesis de trabajo: contrástela con el documento oficial antes de citarla.")

DIMENSIONES_PME_TXT = {"PEDAGOGICA": "Gestión pedagógica", "LIDERAZGO": "Liderazgo",
                       "CONVIVENCIA": "Convivencia escolar", "RECURSOS": "Gestión de recursos"}

# Cada práctica: (texto, raíces de palabras clave). Las raíces se comparan con el comienzo de cada palabra.
MBDLE = [
    {"clave": "vision", "nombre": "Construyendo e implementando una visión estratégica compartida",
     "practicas": [
         ("Construyen, comunican y revisan con la comunidad la visión, misión y sellos del PEI.",
          ["vision", "mision", "sello", "pei", "proyecto educativo", "identidad"]),
         ("Promueven una cultura de altas expectativas sobre los logros de estudiantes y equipos.",
          ["expectativ", "metas de aprendizaje", "logro"]),
         ("Conducen la planificación estratégica y anual (PME) a partir del análisis de datos y el autodiagnóstico.",
          ["diagnost", "autoevalu", "planificacion estrategica", "pme", "analisis de datos", "datos"]),
         ("Monitorean y evalúan el cumplimiento de metas y acciones, y comunican los avances.",
          ["monitore", "seguimiento", "cuenta publica", "evaluacion del pme", "indicador", "metas"]),
     ]},
    {"clave": "capacidades", "nombre": "Desarrollando las capacidades profesionales",
     "practicas": [
         ("Identifican necesidades de desarrollo profesional y gestionan la formación continua.",
          ["capacit", "perfeccion", "formacion continua", "desarrollo profesional", "formacion docente", "taller docente"]),
         ("Acompañan y retroalimentan las prácticas docentes en el aula.",
          ["acompan", "observacion de clase", "retroaliment", "visita al aula", "coaching", "modelamiento"]),
         ("Promueven el trabajo colaborativo y las comunidades profesionales de aprendizaje.",
          ["colaborat", "comunidad de aprendizaje", "comunidades profesionales", "reflexion pedagogica", "consejo de profesores", "codocencia", "co-docencia"]),
         ("Reconocen logros, cuidan el bienestar del equipo e inducen a quienes se incorporan.",
          ["reconoc", "bienestar", "autocuidado", "induccion", "clima laboral"]),
     ]},
    {"clave": "ensenanza", "nombre": "Liderando los procesos de enseñanza y aprendizaje",
     "practicas": [
         ("Aseguran la implementación curricular y la planificación de la enseñanza.",
          ["curricul", "planificacion", "cobertura", "priorizacion", "oa ", "objetivos de aprendizaje", "unidad"]),
         ("Promueven la evaluación para el aprendizaje y el uso de sus resultados.",
          ["evaluacion formativa", "evalu", "simce", "dia ", "resultados de aprendizaje", "decreto 67", "monitoreo de aprendizaje"]),
         ("Apoyan a estudiantes con dificultades y diversifican la enseñanza (inclusión, NEE, PIE).",
          ["nivelac", "reforzamiento", "diversific", "pie", "nee", "inclus", "apoyo pedagogico", "dua", "rezago"]),
         ("Fortalecen las estrategias de enseñanza y el uso de recursos de aprendizaje en el aula.",
          ["estrategias de ensenanza", "metodolog", "lectura", "matematic", "recursos de aprendizaje", "biblioteca", "cra", "tecnolog"]),
     ]},
    {"clave": "convivencia", "nombre": "Gestionando la convivencia y la participación de la comunidad escolar",
     "practicas": [
         ("Promueven un clima de respeto, buen trato y convivencia, con normas y protocolos conocidos.",
          ["convivencia", "buen trato", "clima", "reglamento interno", "protocolo", "mediacion", "socioemocional"]),
         ("Fomentan la participación de estudiantes, familias y consejos (Consejo Escolar, CCAA, CEPA).",
          ["participacion", "familia", "apoderad", "consejo escolar", "centro de alumnos", "centro de padres", "ccaa", "cepa"]),
         ("Desarrollan la formación ciudadana, la inclusión y el respeto a la diversidad.",
          ["formacion ciudadana", "ciudadan", "diversidad", "inclus", "genero", "interculturalidad"]),
         ("Resguardan la asistencia, la retención y la trayectoria educativa de los estudiantes.",
          ["asistencia", "retencion", "desercion", "trayectoria", "ausentismo", "inasistencia"]),
     ]},
    {"clave": "gestion", "nombre": "Desarrollando y gestionando el establecimiento escolar",
     "practicas": [
         ("Gestionan de forma eficiente los recursos financieros, humanos y materiales (incluida la SEP).",
          ["recurso", "presupuest", "sep", "contratac", "adquisic", "inventario", "rendicion", "financ"]),
         ("Organizan los tiempos, procesos y la normativa para que el establecimiento funcione bien.",
          ["normativa", "organizac", "procedimiento", "horario", "jornada", "administrat"]),
         ("Establecen alianzas con redes externas, el sostenedor y la comunidad local.",
          ["redes", "red de", "alianza", "sostenedor", "convenio", "comunidad local", "municipal", "slep"]),
         ("Cuidan la infraestructura, la seguridad y los espacios de aprendizaje.",
          ["infraestruct", "equipamiento", "mantencion", "seguridad", "espacio", "pise"]),
     ]},
]

NOTA_TERRITORIAL = ("Los focos de la ENEP y los componentes del Modelo de Desarrollo de Capacidades son una síntesis de "
                    "trabajo redactada por Pupitre: verifíquelos con los documentos oficiales de la Dirección de "
                    "Educación Pública antes de citarlos. El PEL y el PAL los registra cada sostenedor.")

# Estrategia Nacional de Educación Pública (ENEP 2020-2028), síntesis por focos.
ENEP = [
    {"clave": "enep", "nombre": "Estrategia Nacional de Educación Pública (ENEP)", "practicas": [
        ("Aprendizajes integrales y de calidad para todos los estudiantes.",
         ["aprendizaje", "calidad", "habilidades", "lectura", "matematic", "integral", "socioemocional"]),
        ("Trayectorias educativas completas: asistencia, retención y transiciones entre niveles.",
         ["trayectoria", "asistencia", "retencion", "desercion", "transicion", "egreso", "reingreso"]),
        ("Liderazgo y desarrollo profesional de directivos, docentes y asistentes de la educación.",
         ["liderazgo", "desarrollo profesional", "capacit", "acompan", "retroaliment", "formacion docente"]),
        ("Trabajo colaborativo y en red entre establecimientos del territorio.",
         ["colaborat", "redes", "red de", "comunidad de aprendizaje", "comunidades profesionales", "pasant"]),
        ("Participación de las comunidades educativas y vinculación con el territorio.",
         ["participacion", "familia", "apoderad", "consejo escolar", "territorio", "comunidad local", "vinculacion"]),
        ("Condiciones para el aprendizaje: recursos, infraestructura y bienestar.",
         ["recurso", "infraestruct", "equipamiento", "bienestar", "convivencia", "espacio"]),
    ]},
]

# Modelo de Desarrollo de Capacidades (Dirección de Educación Pública), síntesis por componentes.
MDC = [
    {"clave": "mdc", "nombre": "Modelo de Desarrollo de Capacidades", "practicas": [
        ("Liderazgo directivo y técnico-pedagógico centrado en la mejora.",
         ["liderazgo", "equipo directivo", "ele", "utp", "gestion pedagogica"]),
        ("Desarrollo profesional situado: acompañamiento y retroalimentación en aula.",
         ["acompan", "retroaliment", "observacion de clase", "desarrollo profesional", "modelamiento"]),
        ("Trabajo colaborativo docente y redes de mejoramiento entre escuelas.",
         ["colaborat", "redes", "red de", "comunidad de aprendizaje", "reflexion pedagogica", "codocencia"]),
        ("Uso de datos y ciclos de mejora (diagnóstico, monitoreo y evaluación).",
         ["datos", "diagnost", "monitore", "seguimiento", "analisis de resultados", "dia ", "evaluacion"]),
        ("Apoyo técnico-pedagógico del sostenedor a los establecimientos.",
         ["sostenedor", "slep", "asesoria", "apoyo tecnico", "ate"]),
    ]},
]

_STOP = set("""a al algo ante antes con contra cual cuales cuando de del desde donde dos e el ella ellas ellos en entre
era es esa ese eso esta este esto estos estas fin hacia hasta la las le les lo los mas me mediante mi muy ni no nos o
otra otro para pero por porque que se segun ser si sin sobre su sus tambien tanto te todo todos toda todas tras un una
uno unos unas y ya cada como forma traves través manera nivel niveles estudiante estudiantes establecimiento escuela
liceo comunidad educativa educativo educativos educativas educacion escolar escolares accion acciones plan año ano anual
mejorar fortalecer desarrollar promover implementar lograr logro mediante proceso procesos docente docentes curso
cursos clase clases equipo equipos actividad actividades taller talleres trabajo apoyo apoyos instalar aplicar realizar
generar asegurar contar programa programas plan planes general integral calidad""".split())


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ñ ]+", " ", t)).strip()


def raices(texto, largo=5):
    """Raíces (primeras letras) de las palabras significativas de un texto."""
    return {p[:largo] for p in normalizar(texto).split() if len(p) >= 4 and p not in _STOP}


def _contiene(texto_norm, clave):
    clave = normalizar(clave) if not clave.endswith(" ") else normalizar(clave) + " "
    if " " in clave.strip():
        return clave.strip() in texto_norm
    return re.search(r"\b" + re.escape(clave), texto_norm) is not None


# ------------------------------------------------------------------------------------- elementos a revisar

def elementos_pme(plan, documento=None):
    """Acciones y objetivos del PME (los registrados en Pupitre y los leídos del archivo)."""
    elementos = []
    if plan.objetivo_general.strip():
        elementos.append({"origen": "Objetivo", "dimension": "", "titulo": plan.objetivo_general.strip()[:160],
                          "texto": plan.objetivo_general, "accion": None})
    nombres = set()
    for a in plan.acciones.all():
        nombres.add(normalizar(a.nombre))
        elementos.append({"origen": "Acción", "dimension": a.dimension, "titulo": a.nombre,
                          "texto": f"{a.nombre}. {a.descripcion} {a.medios_verificacion}", "accion": a})
    if documento:
        datos = documento.datos or {}
        for o in datos.get("objetivos", []):
            elementos.append({"origen": "Objetivo (archivo)", "dimension": o.get("dimension", ""),
                              "titulo": o["texto"][:160], "texto": o["texto"], "accion": None})
        for m in datos.get("metas", []):
            elementos.append({"origen": "Meta (archivo)", "dimension": m.get("dimension", ""),
                              "titulo": m["texto"][:160], "texto": m["texto"], "accion": None})
        for a in datos.get("acciones", []):
            if normalizar(a.get("nombre", "")) in nombres:
                continue
            elementos.append({"origen": "Acción (archivo)", "dimension": a.get("dimension", ""),
                              "titulo": a.get("nombre", "")[:160],
                              "texto": f"{a.get('nombre', '')}. {a.get('descripcion', '')}", "accion": None})
    return elementos


# ------------------------------------------------------------------------------------- análisis

def coherencia_pei(pei, elementos):
    """Para cada sello y objetivo del PEI, qué elementos del PME lo abordan."""
    filas = []
    textos = [(e, normalizar(e["texto"]), raices(e["texto"])) for e in elementos]
    vinculados = set()
    componentes = ([("Sello", s) for s in pei.lista_sellos()] + [("Objetivo PEI", o) for o in pei.lista_objetivos()]
                   if pei else [])
    for tipo, texto in componentes:
        r = raices(texto)
        necesarias = 1  # basta una palabra significativa en común (las palabras comunes del ámbito escolar no cuentan)
        coincide = []
        for i, (e, norm, re_) in enumerate(textos):
            comunes = r & re_
            if len(comunes) >= necesarias or (normalizar(texto) and normalizar(texto) in norm):
                coincide.append((e, sorted(comunes)))
                vinculados.add(i)
        filas.append({"tipo": tipo, "texto": texto, "elementos": coincide})
    # la misión y la visión, como conjunto
    mv = raices(f"{pei.mision} {pei.vision} {pei.valores}") if pei else set()
    for i, (e, norm, re_) in enumerate(textos):
        if mv and len(mv & re_) >= 2:
            vinculados.add(i)
    acciones = [i for i, (e, _, _) in enumerate(textos) if e["origen"].startswith("Acción")]
    sin_vinculo = [textos[i][0] for i in acciones if i not in vinculados]
    sellos = [f for f in filas if f["tipo"] == "Sello"]
    cubiertos = sum(1 for f in sellos if f["elementos"])
    pct_sellos = round(100 * cubiertos / len(sellos)) if sellos else None
    pct_acciones = round(100 * (len(acciones) - len(sin_vinculo)) / len(acciones)) if acciones else None
    partes = [p for p in (pct_sellos, pct_acciones) if p is not None]
    return {"filas": filas, "sin_vinculo": sin_vinculo, "sellos_total": len(sellos), "sellos_cubiertos": cubiertos,
            "pct_sellos": pct_sellos, "acciones_total": len(acciones),
            "acciones_vinculadas": len(acciones) - len(sin_vinculo), "pct_acciones": pct_acciones,
            "indice": round(sum(partes) / len(partes)) if partes else None}


def cobertura_mbdle(elementos, marco=None):
    resultado = []
    for dim in marco or MBDLE:
        practicas = []
        for texto, claves in dim["practicas"]:
            hits = [e for e in elementos if any(_contiene(normalizar(e["texto"]) + " ", c) for c in claves)]
            practicas.append({"texto": texto, "elementos": hits})
        cubiertas = sum(1 for p in practicas if p["elementos"])
        resultado.append({"clave": dim["clave"], "nombre": dim["nombre"], "practicas": practicas,
                          "cubiertas": cubiertas, "total": len(practicas),
                          "pct": round(100 * cubiertas / len(practicas))})
    return resultado


def alinear_textos(componentes, elementos):
    """[(etiqueta, texto)] de un plan (PEL, PAL) → qué elementos del PME abordan cada uno."""
    textos = [(e, raices(e["texto"])) for e in elementos]
    filas = []
    for etiqueta, texto in componentes:
        r = raices(texto)
        filas.append({"tipo": etiqueta, "texto": texto, "elementos": [e for e, re_ in textos if r & re_]})
    cubiertos = sum(1 for f in filas if f["elementos"])
    return {"filas": filas, "cubiertos": cubiertos, "total": len(filas),
            "pct": round(100 * cubiertos / len(filas)) if filas else None}


def alineamiento_territorial(sostenedor, anio, elementos):
    """Alineamiento del PME con el PEL y el PAL del sostenedor, la ENEP y el Modelo de Desarrollo de Capacidades."""
    from .models import InstrumentoTerritorial
    if not sostenedor or not (sostenedor.es_slep or sostenedor.instrumentos.exists()):
        return None
    planes = []
    for inst in InstrumentoTerritorial.vigentes(sostenedor, anio):
        a = alinear_textos([(inst.tipo, o) for o in inst.lista_objetivos()], elementos)
        a["instrumento"] = inst
        planes.append(a)
    enep = cobertura_mbdle(elementos, ENEP)[0]
    mdc = cobertura_mbdle(elementos, MDC)[0]
    partes = [p["pct"] for p in planes if p["pct"] is not None] + ([enep["pct"]] if sostenedor.es_slep else [])
    return {"planes": planes, "enep": enep if sostenedor.es_slep else None, "mdc": mdc if sostenedor.es_slep else None,
            "indice": round(sum(partes) / len(partes)) if partes else None, "sostenedor": sostenedor}


def calidad_acciones(plan):
    filas = []
    for a in plan.acciones.all():
        faltas = []
        if len(a.descripcion.strip()) < 60:
            faltas.append("descripción breve o vacía")
        if not a.responsable.strip():
            faltas.append("sin responsable")
        if not (a.inicio and a.termino):
            faltas.append("sin fechas")
        if not a.medios_verificacion.strip():
            faltas.append("sin medios de verificación")
        if not a.monto_sep:
            faltas.append("sin monto asignado")
        filas.append({"accion": a, "faltas": faltas})
    return filas


def sugerencias(pei, plan, coherencia, mbdle, calidad, territorial=None):
    """Sugerencias automáticas: [(nivel, texto)]."""
    s = []
    if territorial:
        for p in territorial["planes"]:
            faltan = [f["texto"] for f in p["filas"] if not f["elementos"]]
            if faltan:
                s.append(("warning", f"{p['instrumento'].get_tipo_display()}: {len(faltan)} de {p['total']} objetivos no "
                                     f"tienen acciones en el PME ({'; '.join(faltan[:4])}{'…' if len(faltan) > 4 else ''})."))
        for marco in (territorial["enep"], territorial["mdc"]):
            if marco:
                faltan = [x["texto"].rstrip(".").lower() for x in marco["practicas"] if not x["elementos"]]
                if faltan:
                    s.append(("info", f"{marco['nombre']}: sin acciones en {'; '.join(faltan)}."))
    if not pei or not pei.completo:
        s.append(("warning", "Complete la visión, la misión y los sellos del PEI para medir la coherencia del PME con el proyecto del establecimiento."))
    for f in coherencia["filas"]:
        if f["tipo"] == "Sello" and not f["elementos"]:
            s.append(("danger", f"El sello «{f['texto']}» no aparece en ninguna acción ni objetivo del PME. "
                                "Considere una acción que lo haga visible en la gestión anual o explicítelo en una acción existente."))
    if coherencia["sin_vinculo"]:
        s.append(("warning", f"{len(coherencia['sin_vinculo'])} acción(es) no se relacionan con los sellos ni con la "
                             "misión y visión. Explicite en su descripción a qué sello u objetivo del PEI contribuyen."))
    acciones = list(plan.acciones.all())
    for clave, nombre in DIMENSIONES_PME_TXT.items():
        n = sum(1 for a in acciones if a.dimension == clave)
        if n == 0:
            s.append(("danger", f"La dimensión {nombre} no tiene acciones registradas."))
        elif n == 1:
            s.append(("info", f"La dimensión {nombre} tiene una sola acción: revise si basta para lograr su objetivo."))
    for d in mbdle:
        faltan = [p["texto"].rstrip(".") for p in d["practicas"] if not p["elementos"]]
        if faltan:
            s.append(("danger" if len(faltan) == len(d["practicas"]) else "info",
                      f"Marco para la Buena Dirección · {d['nombre']}: {len(faltan)} de {len(d['practicas'])} prácticas "
                      f"sin acciones ({'; '.join(f.lower() for f in faltan)})."))
    sin_medios = sum(1 for c in calidad if "sin medios de verificación" in c["faltas"])
    if sin_medios:
        s.append(("warning", f"{sin_medios} acción(es) no tienen medios de verificación: son necesarios para la rendición y el monitoreo."))
    breves = sum(1 for c in calidad if "descripción breve o vacía" in c["faltas"])
    if breves:
        s.append(("info", f"{breves} acción(es) tienen una descripción muy breve: indique qué se hará, con quiénes, con qué frecuencia y qué resultado se espera."))
    return s


# ------------------------------------------------------------------------------------- lectura de archivos

def extraer_texto(nombre, contenido):
    """Texto plano de un PDF, Word, Excel o texto. Lanza ValueError si el formato no se puede leer."""
    ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
    if ext == "pdf":
        from pypdf import PdfReader
        try:
            lector = PdfReader(BytesIO(contenido))
            return "\n".join((p.extract_text() or "") for p in lector.pages)
        except Exception as e:  # PDF dañado o protegido
            raise ValueError("No se pudo leer el PDF. Si está protegido o escaneado, descárguelo en Excel.") from e
    if ext == "docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        doc = Document(BytesIO(contenido))
        lineas = []
        for hijo in doc.element.body.iterchildren():  # párrafos y tablas en el orden del documento
            etiqueta = hijo.tag.rsplit("}", 1)[-1]
            if etiqueta == "p":
                lineas.append(Paragraph(hijo, doc).text)
            elif etiqueta == "tbl":
                for fila in Table(hijo, doc).rows:
                    celdas = []
                    for c in fila.cells:
                        if c.text.strip() and c.text.strip() not in celdas:
                            celdas.append(c.text.strip())
                    lineas.append(": ".join(celdas) if len(celdas) == 2 else " | ".join(celdas))
        return "\n".join(lineas)
    if ext in ("xlsx", "xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
        return "\n".join(_lineas_planilla(list(h.iter_rows(values_only=True))) for h in wb.worksheets)
    if ext == "xls":
        import xlrd
        wb = xlrd.open_workbook(file_contents=contenido)
        return "\n".join(_lineas_planilla([h.row_values(i) for i in range(h.nrows)]) for h in wb.sheets())
    if ext in ("txt", "csv"):
        return contenido.decode("utf-8", errors="ignore")
    raise ValueError("Formato no soportado. Suba el PME en PDF, Excel o Word.")


def _lineas_planilla(filas):
    """Si la primera fila con varios textos parece encabezado, cada fila se convierte en «Encabezado: valor»."""
    filas = [[("" if v is None else str(v).strip()) for v in f] for f in filas]
    filas = [f for f in filas if any(f)]
    if not filas:
        return ""
    encabezado, inicio = None, 0
    for i, f in enumerate(filas[:15]):
        if sum(1 for v in f if v) >= 3 and any(re.search(r"acci|nombre|descrip|dimensi|respons", normalizar(v)) for v in f):
            encabezado, inicio = f, i + 1
            break
    lineas = []
    if encabezado:
        for f in filas[inicio:]:
            lineas.append("Nueva fila")
            lineas += [f"{encabezado[j] or 'Columna'}: {v}" for j, v in enumerate(f) if v and j < len(encabezado)]
    else:
        lineas = [": ".join(v for v in f if v) for f in filas]
    return "\n".join(lineas)


_ETIQUETAS = [  # (expresión sobre el texto normalizado al inicio de la línea, campo)
    (r"^(nombre( de la)? accion|accion)\b", "nombre"),
    (r"^descripcion\b", "descripcion"),
    (r"^(responsable|cargo responsable|cargo)\b", "responsable"),
    (r"^(fecha( de)? )?inicio\b", "inicio"),
    (r"^(fecha( de)? )?termino\b", "termino"),
    (r"^medios? de verificacion\b", "medios"),
    (r"^(monto|total)( subvencion)? sep\b|^sep\b", "monto"),
    (r"^(sub)?dimension\b", "dimension_txt"),
    (r"^objetivo estrategico\b|^objetivo\b", "objetivo"),
    (r"^meta estrategica\b|^meta\b", "meta"),
    (r"^estrategia\b", "estrategia"),
]
_DIMENSIONES = [("PEDAGOGICA", r"gestion pedagogica|area pedagogica"), ("LIDERAZGO", r"liderazgo"),
                ("CONVIVENCIA", r"convivencia"), ("RECURSOS", r"gestion de recursos|recursos")]


def _dimension(texto):
    n = normalizar(texto)
    for clave, patron in _DIMENSIONES:
        if re.search(patron, n):
            return clave
    return ""


# ---------------------------------------------------------------- formato del reporte de Comunidad Escolar

_CE_ETIQUETAS = [  # (inicio de la línea normalizada, campo); el valor es el resto de la línea
    ("dimension ", "dimension"), ("objetivo estrategico", "objetivo"), ("estrategia", "estrategia"),
    ("subdimensiones", "subdimension"), ("subdimension", "subdimension"), ("accion ", "nombre"),
    ("descripcion", "descripcion"), ("nivel de ejecucion", "nivel"), ("justificacion de nivel", "justificacion"),
    ("fecha inicio", "inicio"), ("fecha termino", "termino"), ("programa asociado", "programa"),
    ("responsable", "responsable"), ("recursos necesarios ejecucion", "recursos"), ("ate ", "ate"), ("tic ", "tic"),
    ("plan es", "planes"), ("medios de verificacion", "medios"), ("monto sep", "monto"), ("monto total", "monto_total"),
    ("monto ", None),
]


def es_comunidad_escolar(texto):
    return bool(re.search(r"^Planificaci[oó]n Anual", texto, re.M) and re.search(r"^Monto Total", texto, re.M)
                and re.search(r"^Acci[oó]n ", texto, re.M))


def _ce_pei(lineas):
    """Síntesis del PEI del reporte: Visión, Misión, Sello N, Valores y Competencias."""
    pei, actual = {}, None
    try:
        inicio = next(i for i, l in enumerate(lineas) if normalizar(l).startswith("sintesis de los componentes del pei"))
    except StopIteration:
        return {}
    for linea in lineas[inicio + 1:]:
        n = normalizar(linea)
        if n.startswith("vinculacion pei"):
            break
        if n.startswith("vision "):
            actual, pei["vision"] = "vision", linea.split(None, 1)[1]
        elif n.startswith("mision "):
            actual, pei["mision"] = "mision", linea.split(None, 1)[1]
        elif re.match(r"^sello \d+ ", n):
            pei.setdefault("sellos", []).append(linea.split(None, 2)[2].strip())
            actual = "sello"
        elif n.startswith("valores y competencias"):
            actual, pei["valores"] = "valores", ""
        elif actual == "sello":
            pei["sellos"][-1] += " " + linea.strip()
        elif actual:
            pei[actual] = f"{pei[actual]} {linea.strip()}".strip()
    if "sellos" in pei:
        pei["sellos"] = "\n".join(pei["sellos"])
    return {k: v[:3000] for k, v in pei.items() if v}


def _ce_objetivos_metas(lineas):
    """Tabla «Objetivos y Metas»: por dimensión, el objetivo (hasta la primera línea que termina en punto) y la meta."""
    dims = {"gestion pedagogica": "PEDAGOGICA", "liderazgo": "LIDERAZGO", "convivencia escolar": "CONVIVENCIA",
            "gestion de recursos": "RECURSOS", "area de resultados": "RESULTADOS"}
    try:
        inicio = next(i for i, l in enumerate(lineas) if normalizar(l) == "objetivos y metas")
    except StopIteration:
        return [], []
    bloques, actual = [], None
    for linea in lineas[inicio + 1:]:
        n = normalizar(linea)
        if n.startswith("estrategias"):
            break
        if n in dims:
            actual = [dims[n], []]
            bloques.append(actual)
        elif actual is not None:
            actual[1].append(linea.strip())
    objetivos, metas = [], []
    for dim, ls in bloques:
        corte = next((i for i, l in enumerate(ls) if l.endswith(".")), len(ls) - 1) + 1
        objetivo, meta = " ".join(ls[:corte]).strip(), " ".join(ls[corte:]).strip()
        etiqueta = "" if dim == "RESULTADOS" else dim
        prefijo = "Área de resultados: " if dim == "RESULTADOS" else ""
        if objetivo:
            objetivos.append({"dimension": etiqueta, "texto": prefijo + objetivo})
        if meta:
            metas.append({"dimension": etiqueta, "texto": prefijo + meta})
    return objetivos, metas


def _ce_acciones(lineas):
    """Bloques de acciones de «Planificación Anual» y de «Implementación y Monitoreo» (este aporta el nivel de
    ejecución). Las acciones repetidas se fusionan por nombre."""
    acciones, bloque, campo = {}, None, None

    def cerrar():
        if bloque and bloque.get("nombre"):
            clave = normalizar(bloque["nombre"])
            previa = acciones.setdefault(clave, {})
            for k, v in bloque.items():
                if v and not previa.get(k):
                    previa[k] = v

    en_acciones = False
    for linea in lineas:
        n = normalizar(linea)
        if n == "acciones":
            en_acciones = True
            continue
        if n in ("reporte",) or n.startswith("fecha de creacion") or n.startswith("nombre establecimiento"):
            en_acciones = False if n == "reporte" else en_acciones
            continue
        if not en_acciones:
            continue
        etiqueta = next(((e, c) for e, c in _CE_ETIQUETAS if (n + " ").startswith(e)), None)
        if etiqueta:
            e, c = etiqueta
            valor = " ".join(linea.split()[len(e.split()):]).strip(" -")
            if e == "plan es":
                valor = ""
            if c == "dimension":
                cerrar()
                bloque, campo = {"dimension": _dimension(valor)}, None
                continue
            if bloque is None:
                continue
            if c:
                bloque[c] = valor
            # campos de una sola línea: lo que sigue no se les agrega
            campo = None if c in (None, "inicio", "termino", "programa", "ate", "tic", "nivel", "monto",
                                  "monto_total", "responsable") else c
            continue
        if bloque is not None and campo:
            bloque[campo] = f"{bloque.get(campo, '')} {linea.strip()}".strip()
    cerrar()
    lista = []
    for a in acciones.values():
        for k in ("nombre", "descripcion", "medios", "planes", "recursos"):
            if a.get(k):
                a[k] = re.sub(r"\s*-\s*$", "", re.sub(r"-\s+(?=[A-ZÁÉÍÓÚ])", "; ", a[k])).strip()
        a["nombre"] = a["nombre"].rstrip(" .")[:200]
        lista.append(a)
    return lista


def _analizar_comunidad_escolar(texto):
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    objetivos, metas = _ce_objetivos_metas(lineas)
    acciones = _ce_acciones(lineas)
    if not objetivos:  # sin la tabla, se toman los objetivos que acompañan a cada acción
        vistos = set()
        for a in acciones:
            if a.get("objetivo") and normalizar(a["objetivo"]) not in vistos:
                vistos.add(normalizar(a["objetivo"]))
                objetivos.append({"dimension": a.get("dimension", ""), "texto": a["objetivo"]})
    return {"formato": "Comunidad Escolar", "pei": _ce_pei(lineas), "objetivos": objetivos, "metas": metas,
            "acciones": acciones}


def nivel_ejecucion(texto):
    """«Implementado (100%)» → (estado, avance) para AccionPME."""
    m = re.search(r"(\d{1,3})\s*%", texto or "")
    if not m:
        return None
    avance = min(int(m.group(1)), 100)
    return ("EJECUTADA" if avance >= 100 else "PROCESO" if avance > 0 else "NO"), avance


def analizar_pme(texto):
    """Busca objetivos, metas y acciones en el texto del PME. Reconoce el reporte de Comunidad Escolar; para otros
    formatos usa una lectura general por etiquetas («Nombre de la acción: …»)."""
    if es_comunidad_escolar(texto):
        return _analizar_comunidad_escolar(texto)
    objetivos, metas, acciones = [], [], []
    actual, campo, dimension, modo_fila = None, None, "", False
    for linea in (l.strip() for l in texto.splitlines()):
        if not linea:
            continue
        norm = normalizar(linea)
        if norm == "nueva fila":
            if actual and actual.get("nombre"):
                acciones.append(actual)
            actual, campo, modo_fila = {"dimension": ""}, None, True
            continue
        encontrado, palabras_etiqueta = None, 0
        for patron, nombre_campo in _ETIQUETAS:
            m = re.match(patron, norm)
            if m:
                encontrado, palabras_etiqueta = nombre_campo, len(m.group(0).split())
                break
        # Título de dimensión suelto (sin etiqueta): «Gestión Pedagógica», «Dimensión: Liderazgo»
        if not encontrado and len(norm) < 40 and _dimension(linea) and not actual:
            dimension = _dimension(linea)
            continue
        if encontrado:
            # el valor es lo que sigue a la etiqueta (con o sin «:», como en las tablas de un PDF)
            valor = " ".join(linea.split()[palabras_etiqueta:]).lstrip(":-–\t ").strip()
            if encontrado == "nombre":
                if modo_fila and actual is not None and not actual.get("nombre"):
                    actual["nombre"] = valor  # columna de la misma fila
                    actual["dimension"] = actual.get("dimension") or dimension
                else:
                    if actual and actual.get("nombre"):
                        acciones.append(actual)
                    actual = {"dimension": dimension, "nombre": valor}
                campo = "nombre"
            elif encontrado in ("objetivo", "meta", "estrategia"):
                if actual and actual.get("nombre"):
                    acciones.append(actual)
                    actual = None
                lista = objetivos if encontrado == "objetivo" else metas if encontrado == "meta" else None
                if lista is not None:
                    lista.append({"dimension": dimension, "texto": valor})
                campo = encontrado
            elif encontrado == "dimension_txt":
                d = _dimension(valor)
                if d:
                    if modo_fila and actual is not None:
                        actual["dimension"] = d  # columna de la fila actual
                    else:
                        if actual and actual.get("nombre"):
                            acciones.append(actual)
                            actual = None
                        dimension = d
                campo = None
            elif actual is not None:
                actual[encontrado] = valor
                campo = encontrado
            continue
        # continuación del campo anterior
        if campo in ("objetivo", "meta") and (objetivos if campo == "objetivo" else metas):
            item = (objetivos if campo == "objetivo" else metas)[-1]
            item["texto"] = f"{item['texto']} {linea}".strip()
        elif actual is not None and campo:
            actual[campo] = f"{actual.get(campo, '')} {linea}".strip()
    if actual and actual.get("nombre"):
        acciones.append(actual)
    limpiar = lambda lista: [x for x in lista if len(x.get("texto", x.get("nombre", ""))) >= 8]
    for a in acciones:
        a["nombre"] = a["nombre"][:200]
    return {"objetivos": limpiar(objetivos), "metas": limpiar(metas), "acciones": limpiar(acciones)}


def leer_pei(texto):
    """Intenta ubicar visión, misión y sellos en el texto de un PEI. Devuelve solo lo que encuentra."""
    if "sintesis de los componentes del pei" in normalizar(texto):
        pei = _ce_pei([l.strip() for l in texto.splitlines() if l.strip()])
        if pei:
            return pei
    secciones = {"vision": r"^vision\b", "mision": r"^mision\b", "sellos": r"^sellos?( educativos?)?\b",
                 "valores": r"^(valores|perfil del estudiante|perfil de egreso|competencias)\b"}
    encontrado, actual = {}, None
    for linea in (l.strip() for l in texto.splitlines()):
        if not linea:
            continue
        norm = normalizar(linea)
        nuevo = next((k for k, p in secciones.items() if re.match(p, norm) and len(norm) < 60), None)
        if nuevo:
            actual = nuevo
            resto = re.split(r"[:.]", linea, maxsplit=1)[1].strip() if re.search(r"[:.]", linea) else ""
            encontrado.setdefault(actual, [])
            if resto:
                encontrado[actual].append(resto)
            continue
        if actual and (re.match(r"^(\d+(\.\d+)*\.?|[ivx]+\.)\s+[A-ZÁÉÍÓÚ]", linea) and len(linea) < 70):
            actual = None  # empieza otra sección numerada
            continue
        if actual and len(encontrado[actual]) < 15:
            encontrado[actual].append(linea)
    resultado = {}
    for k, lineas in encontrado.items():
        if k == "sellos":
            resultado[k] = "\n".join(l.strip(" -•*") for l in lineas if 2 < len(l) < 160)
        else:
            resultado[k] = " ".join(lineas)[:2000]
    return {k: v for k, v in resultado.items() if v.strip()}


# ------------------------------------------------------------------------------------- IA (opcional)

SISTEMA_IA = (
    "Eres un asesor técnico-pedagógico chileno que revisa Planes de Mejoramiento Educativo (PME). Analiza la "
    "coherencia del PME con el Proyecto Educativo Institucional (PEI) y su relación con el Marco para la Buena "
    "Dirección y el Liderazgo Escolar (Mineduc, 2015). Responde en español de Chile, en tono respetuoso y concreto, "
    "con estas secciones breves: 1) Fortalezas, 2) Brechas de coherencia con el PEI, 3) Relación con el Marco para "
    "la Buena Dirección, 4) Sugerencias concretas para enriquecer las acciones (máximo 8). No inventes datos que no "
    "estén en el texto. Si citas normativa, indica que debe verificarse.")


def texto_para_ia(pei, plan, elementos, territorial=None):
    partes = [f"PME {plan.anio}."]
    if territorial:
        for p in territorial["planes"]:
            partes.append(f"{p['instrumento'].get_tipo_display()} del sostenedor: " + "; ".join(f["texto"] for f in p["filas"]))
        if territorial["enep"]:
            partes.append("El sostenedor es un SLEP: considera también la Estrategia Nacional de Educación Pública y el "
                          "Modelo de Desarrollo de Capacidades de la Dirección de Educación Pública.")
    if pei:
        partes += [f"Visión: {pei.vision}", f"Misión: {pei.mision}", "Sellos: " + "; ".join(pei.lista_sellos()),
                   f"Valores y perfil: {pei.valores}", "Objetivos del PEI: " + "; ".join(pei.lista_objetivos())]
    for e in elementos:
        dim = DIMENSIONES_PME_TXT.get(e["dimension"], "")
        partes.append(f"- [{e['origen']}{' · ' + dim if dim else ''}] {e['texto'][:600]}")
    return "\n".join(partes)[:60000]


def revision_ia(pei, plan, elementos, territorial=None):
    """Devuelve (texto, error). Solo envía el PEI y el contenido del PME, sin datos de estudiantes."""
    from .asistente import consultar_ia
    return consultar_ia(SISTEMA_IA, texto_para_ia(pei, plan, elementos, territorial), "El servicio no pudo revisar este PME.")
