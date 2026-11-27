"""Currículum nacional precargado y asistente de planificación (funciona sin internet, sin IA).

Los OA precargados son los Aprendizajes Basales de la Actualización de la Priorización Curricular (Mineduc)
para Lenguaje, Matemática, Ciencias Naturales e Historia, de 1° básico a II medio. El texto de cada OA es una
síntesis fiel; el texto oficial completo está en curriculumnacional.cl. Cada establecimiento puede agregar o
importar desde Excel los OA que falten (complementarios, otras asignaturas, módulos TP).

El asistente propone una clase (inicio, desarrollo, cierre) y evaluaciones formativas y sumativas a partir del
verbo del OA (taxonomía de Bloom) y de la asignatura, y una evaluación de unidad según lo planificado en el
leccionario.
"""
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

CARPETA = Path(__file__).resolve().parent / "curriculum"
ARCHIVOS = {"lenguaje": "lenguaje.txt", "matematica": "matematica.txt", "ciencias": "ciencias.txt",
            "historia": "historia.txt"}
ROMANOS = {"I": 9, "II": 10, "III": 11, "IV": 12}


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


def grado_desde_texto(texto):
    """'5° básico' → 5 · 'I medio' / '1° medio' → 9 · '8' → 8."""
    t = _sin_tildes(texto).strip()
    m = re.match(r"^(iv|iii|ii|i)\s*(°|º)?\s*(ano\s+)?medio", t)
    if m:
        return ROMANOS[m.group(1).upper()]
    m = re.match(r"^([1-8])\s*(°|º|o)?\s*(ano\s+)?(basico|medio)?", t)
    if not m:
        return None
    n = int(m.group(1))
    if m.group(4) == "medio":
        return n + 8 if n <= 4 else None
    return n


def grado_de_curso(curso):
    return grado_desde_texto(curso.nivel.nombre) if curso and curso.nivel_id else None


def clave_asignatura(nombre):
    """Asignatura del establecimiento → clave del currículum."""
    n = _sin_tildes(nombre)
    reglas = [("lengua", "lenguaje"), ("matemat", "matematica"), ("ciencias nat", "ciencias"), ("biolog", "ciencias"),
              ("fisica", "ciencias"), ("quimic", "ciencias"), ("ciencias para", "ciencias"), ("historia", "historia"),
              ("ingles", "ingles"), ("artes", "artes"), ("musica", "musica"), ("educacion fis", "educacion_fisica"),
              ("tecnolog", "tecnologia"), ("orientacion", "orientacion"), ("religion", "religion")]
    if "educacion fis" in n:
        return "educacion_fisica"
    for patron, clave in reglas:
        if patron in n:
            return clave
    return "otra"


def leer_archivo(clave):
    """Filas (grado, numero, texto) del archivo precargado de una asignatura."""
    filas = []
    for linea in (CARPETA / ARCHIVOS[clave]).read_text(encoding="utf-8").splitlines():
        partes = [p.strip() for p in linea.split("|")]
        if len(partes) != 3:
            continue
        grado = grado_desde_texto(partes[0])
        numero = re.sub(r"\D", "", partes[1])
        if grado and numero:
            filas.append((grado, int(numero), partes[2]))
    return filas


def cargar_oficiales(modelo):
    """Crea o actualiza los OA oficiales precargados. Idempotente; nunca toca los OA propios de un establecimiento."""
    creados = 0
    for clave in ARCHIVOS:
        for grado, numero, texto in leer_archivo(clave):
            _, creado = modelo.objects.update_or_create(
                establecimiento=None, asignatura=clave, grado=grado, numero=numero,
                defaults={"texto": texto, "basal": True})
            creados += creado
    return creados


def oas_para(ac, anteriores=False):
    """OA disponibles para una asignatura de un curso (oficiales + propios del establecimiento).

    anteriores=True incluye los de niveles anteriores de la misma asignatura (nivelación).
    """
    from .models import ObjetivoAprendizaje

    grado = grado_de_curso(ac.curso)
    clave = clave_asignatura(ac.asignatura.nombre)
    if grado is None:
        return ObjetivoAprendizaje.objects.none()
    filtro = {"grado__lte": grado} if anteriores else {"grado": grado}
    return ObjetivoAprendizaje.disponibles().filter(asignatura=clave, **filtro)


# --------------------------------------------------------------------------- asistente (reglas, sin IA)

NIVELES_BLOOM = OrderedDict([
    ("crear", ["crear", "disenar", "escribir", "planificar", "proponer", "producir", "componer", "inventar",
               "elaborar", "construir textos", "aplicar escritura", "expresarse", "exponer", "desempenar",
               "caracterizar distintos", "participar", "dialogar", "experimentar con la escritura"]),
    ("evaluar", ["evaluar", "argumentar", "fundamentar", "juzgar", "valorar", "debatir", "interpretar"]),
    ("analizar", ["analizar", "comparar", "relacionar", "investigar", "contrastar", "distinguir", "conjeturar",
                  "evidenciar", "demostrar", "modelar", "crear modelos"]),
    ("aplicar", ["aplicar", "resolver", "calcular", "usar", "medir", "construir", "representar", "multiplicar",
                 "dividir", "sumar", "restar", "realizar", "descomponer", "ordenar", "trasladar", "estimar",
                 "registrar", "recopilar", "practicar", "asumir", "leer"]),
    ("comprender", ["comprender", "explicar", "describir", "clasificar", "caracterizar", "ejemplificar",
                    "reconocer", "demostrar comprension", "profundizar", "obtener", "conocer", "sintetizar"]),
    ("recordar", ["identificar", "ubicar", "nombrar", "localizar", "observar", "explorar", "desarrollar el gusto"]),
])

NOMBRE_NIVEL = {"recordar": "Recordar / identificar", "comprender": "Comprender", "aplicar": "Aplicar",
                "analizar": "Analizar", "evaluar": "Evaluar", "crear": "Crear / producir"}


def nivel_bloom(texto):
    t = _sin_tildes(texto)
    inicio = re.sub(r"^oa\s*\d+\s*[:.-]?\s*", "", t)
    for nivel, verbos in NIVELES_BLOOM.items():
        if any(inicio.startswith(v) for v in verbos):
            return nivel
    for nivel, verbos in NIVELES_BLOOM.items():  # el verbo no está al inicio: busca en el texto
        if any(re.search(rf"\b{v}", inicio) for v in verbos):
            return nivel
    return "comprender"


def _verbo(texto):
    m = re.match(r"^(?:OA\s*\d+\s*[:.-]?\s*)?(\w+)", texto.strip(), re.IGNORECASE)
    return (m.group(1) if m else "lograr").lower()


def _contenido(texto):
    """El OA sin su verbo inicial ni el N°: 'las cuatro operaciones ...'."""
    t = re.sub(r"^(?:OA\s*\d+\s*[:.-]?\s*)?\w+\s+", "", texto.strip(), flags=re.IGNORECASE)
    return t.rstrip(".")


DESARROLLO = {
    "matematica": {
        "recordar": ["Exploración con material concreto (bloques, fichas, tarjetas) para identificar el concepto.",
                     "Juego de reconocimiento en parejas con tarjetas de ejemplos y no ejemplos."],
        "comprender": ["Modelamiento docente con el enfoque concreto-pictórico-simbólico (COPISI).",
                       "Los estudiantes explican con sus palabras y con un dibujo el procedimiento a un compañero."],
        "aplicar": ["Práctica guiada: resolución de 3 problemas en pizarra con participación de los estudiantes.",
                    "Práctica independiente graduada (fácil, intermedio, desafío) en la guía de trabajo.",
                    "Resolución de un problema contextualizado de la vida cotidiana, comunicando la estrategia."],
        "analizar": ["Comparación de dos estrategias de resolución: ¿cuál es más eficiente y por qué?",
                     "Análisis de errores frecuentes en ejercicios resueltos (detective del error)."],
        "evaluar": ["Validación de respuestas: los grupos justifican si un resultado es razonable.",
                    "Debate breve sobre qué representación conviene usar en distintos problemas."],
        "crear": ["Los estudiantes inventan un problema para el compañero y lo resuelven en pareja.",
                  "Diseño de un juego o situación que requiera aplicar el contenido."],
    },
    "lenguaje": {
        "recordar": ["Lectura compartida con identificación de información explícita.",
                     "Juego de vocabulario: palabras clave del texto en tarjetas."],
        "comprender": ["Lectura guiada con estrategias de comprensión (predecir, preguntar, resumir).",
                       "Organizador gráfico de la secuencia o de las ideas principales del texto."],
        "aplicar": ["Lectura en voz alta en parejas con retroalimentación de fluidez.",
                    "Aplicación de la estrategia trabajada en un texto nuevo, de forma individual."],
        "analizar": ["Análisis en grupos de personajes, conflicto o recursos del texto con evidencia textual.",
                     "Comparación de dos textos (tema, propósito, recursos) en una tabla de doble entrada."],
        "evaluar": ["Discusión socrática: los estudiantes fundamentan su opinión con citas del texto.",
                    "Evaluación de la confiabilidad de fuentes o del punto de vista de un texto."],
        "crear": ["Planificación del texto (propósito, destinatario, ideas) con un organizador.",
                  "Escritura del borrador y revisión entre pares con pauta breve.",
                  "Presentación oral o lectura de las producciones al curso."],
    },
    "ciencias": {
        "recordar": ["Observación directa de muestras, láminas o videos breves con registro en el cuaderno.",
                     "Clasificación de tarjetas o imágenes según características observables."],
        "comprender": ["Explicación con modelos (maqueta, diagrama o simulación) del fenómeno estudiado.",
                       "Lectura de un texto científico breve y elaboración de un esquema."],
        "aplicar": ["Actividad práctica guiada: medir, registrar datos en tabla y graficar.",
                    "Aplicación del concepto a una situación cotidiana o del entorno local."],
        "analizar": ["Experimento en grupos siguiendo las etapas de la investigación científica (pregunta, hipótesis, "
                     "procedimiento, resultados).",
                     "Análisis de datos y elaboración de conclusiones a partir de evidencia."],
        "evaluar": ["Debate sobre un problema socio-científico usando evidencia.",
                    "Evaluación de medidas de cuidado o de los efectos de la acción humana."],
        "crear": ["Diseño de un modelo o prototipo que explique el fenómeno.",
                  "Elaboración de una campaña o propuesta para la comunidad escolar."],
    },
    "historia": {
        "recordar": ["Ubicación en mapas y líneas de tiempo de los hechos, lugares y actores principales.",
                     "Lectura de una fuente breve y subrayado de información clave."],
        "comprender": ["Análisis guiado de una fuente primaria o iconográfica con preguntas.",
                       "Elaboración de un organizador gráfico de causas, características y consecuencias."],
        "aplicar": ["Trabajo con mapas temáticos o líneas de tiempo para situar el proceso estudiado.",
                    "Aplicación de conceptos a la realidad local o regional."],
        "analizar": ["Comparación de dos fuentes o visiones sobre un mismo hecho.",
                     "Análisis de continuidades y cambios entre el pasado y el presente."],
        "evaluar": ["Debate o juicio histórico fundamentado en fuentes.",
                    "Escritura de una opinión fundamentada sobre el proceso estudiado."],
        "crear": ["Diseño de un proyecto o propuesta para la comunidad escolar.",
                  "Elaboración de un afiche, cápsula o exposición sobre el tema investigado."],
    },
}
DESARROLLO_GENERAL = {
    "recordar": ["Actividad de exploración e identificación con apoyo visual o material concreto."],
    "comprender": ["Explicación del docente con ejemplos y modelamiento.",
                   "Trabajo en parejas: explicar el concepto con sus palabras y un ejemplo propio."],
    "aplicar": ["Práctica guiada y luego independiente de la habilidad.",
                "Aplicación en una situación nueva o del contexto de los estudiantes."],
    "analizar": ["Trabajo en grupos para comparar, clasificar y relacionar la información.",
                 "Análisis de casos o ejemplos con preguntas orientadoras."],
    "evaluar": ["Discusión guiada donde los estudiantes fundamentan sus juicios con criterios.",
                "Coevaluación de trabajos con una pauta simple."],
    "crear": ["Diseño y elaboración de un producto o presentación.",
              "Retroalimentación entre pares y mejora del producto."],
}

FORMATIVAS = {
    "recordar": [("Pizarras individuales", "Todos responden a la vez en una pizarra o papel; el docente revisa de un vistazo y reenseña si hace falta."),
                 ("Ticket de salida", "Dos preguntas breves al cierre para identificar el concepto trabajado.")],
    "comprender": [("Pregunta bisagra", "Una pregunta de alternativas cuyas opciones incorrectas revelan errores típicos; se hace a mitad de clase."),
                   ("Explícale a un compañero", "En parejas, cada uno explica el concepto; el docente escucha y registra."),
                   ("Ticket de salida", "Explicar con sus palabras la idea central y dar un ejemplo.")],
    "aplicar": [("Semáforo de autoevaluación", "Cada estudiante marca verde, amarillo o rojo según cómo resolvió; se agrupan para apoyo."),
                ("Ejercicio de verificación", "Un ejercicio al final de la práctica guiada; quien lo resuelve avanza al desafío."),
                ("Ticket de salida", "Un problema breve similar a los trabajados, revisado al día siguiente.")],
    "analizar": [("Rutina de pensamiento «Veo, pienso, me pregunto»", "Registro escrito breve que muestra el razonamiento."),
                 ("Coevaluación con pauta", "Los grupos revisan el análisis de otro grupo con 3 criterios."),
                 ("Ticket de salida", "¿En qué se parecen y en qué se diferencian…? con evidencia.")],
    "evaluar": [("Escalera de retroalimentación", "Aclarar, valorar, expresar inquietudes y sugerir, entre pares."),
                ("Registro de argumentos", "El docente registra en una lista de cotejo la calidad de los argumentos durante la discusión.")],
    "crear": [("Revisión de borrador con pauta", "Retroalimentación del docente o de pares sobre el borrador antes de la versión final."),
              ("Autoevaluación con rúbrica", "Los estudiantes revisan su producto con la misma rúbrica con que serán calificados.")],
}

SUMATIVAS = {
    "recordar": ("Prueba escrita breve", "Ítems de selección múltiple, términos pareados y completación (60 %) más preguntas de respuesta corta (40 %)."),
    "comprender": ("Prueba escrita", "Selección múltiple (40 %) y preguntas de desarrollo breve en que expliquen con sus palabras y den ejemplos (60 %)."),
    "aplicar": ("Prueba de resolución de problemas", "Ejercicios y problemas graduados en dificultad; se evalúa procedimiento y resultado con pauta de corrección."),
    "analizar": ("Informe o análisis de caso", "Análisis escrito de un caso, fuente o experimento, evaluado con rúbrica analítica."),
    "evaluar": ("Debate o ensayo argumentativo", "Postura fundamentada con evidencia, evaluada con rúbrica (tesis, argumentos, evidencia, contraargumento)."),
    "crear": ("Proyecto o producto final", "Producción (texto, maqueta, presentación, campaña) evaluada con rúbrica conocida desde el inicio."),
}

CRITERIOS_RUBRICA = {
    "recordar": ["Identifica correctamente los conceptos", "Usa vocabulario de la asignatura"],
    "comprender": ["Explica con sus palabras", "Da ejemplos pertinentes", "Usa vocabulario de la asignatura"],
    "aplicar": ["Selecciona el procedimiento adecuado", "Ejecuta el procedimiento sin errores", "Comunica y verifica el resultado"],
    "analizar": ["Identifica elementos o variables relevantes", "Establece relaciones con evidencia", "Formula conclusiones coherentes"],
    "evaluar": ["Presenta una postura clara", "Fundamenta con evidencia", "Considera otras posturas", "Comunica con claridad"],
    "crear": ["Cumple el propósito y el destinatario", "Organización y estructura", "Originalidad y creatividad", "Corrección y presentación"],
}
NIVELES_LOGRO = ["Logrado (3 pts.)", "Medianamente logrado (2 pts.)", "Por lograr (1 pt.)"]


def proponer_clase(oa_texto, clave_asig, bloques=2):
    """Propuesta de clase a partir del OA: inicio, desarrollo, cierre y evaluación formativa."""
    nivel = nivel_bloom(oa_texto)
    contenido = _contenido(oa_texto)
    banco = DESARROLLO.get(clave_asig, {}).get(nivel) or DESARROLLO_GENERAL[nivel]
    minutos = 45 * bloques
    inicio_min, cierre_min = round(minutos * 0.15), round(minutos * 0.15)
    formativa = FORMATIVAS[nivel][0]
    inicio = (f"Inicio ({inicio_min} min): se comparte el objetivo de la clase y se activan conocimientos previos "
              f"con una pregunta o situación desafiante sobre {contenido[:90].rstrip(',;')}.")
    desarrollo = f"Desarrollo ({minutos - inicio_min - cierre_min} min): " + " ".join(banco)
    if len(FORMATIVAS[nivel]) > 1:
        desarrollo += f" Monitoreo formativo: {FORMATIVAS[nivel][1][0].lower()}."
    cierre = (f"Cierre ({cierre_min} min): síntesis de lo aprendido con los estudiantes y {formativa[0].lower()}: "
              f"{formativa[1][0].lower() + formativa[1][1:]}")
    return {
        "nivel": nivel, "nivel_nombre": NOMBRE_NIVEL[nivel],
        "objetivo_clase": f"{_verbo(oa_texto).capitalize()} {contenido}.",
        "actividades": "\n".join([inicio, desarrollo, cierre]),
        "recursos": _recursos(clave_asig, nivel),
        "formativas": [{"nombre": n, "descripcion": d} for n, d in FORMATIVAS[nivel]],
        "sumativa": _sumativa([(oa_texto, 1)]),
        "indicadores": indicadores(oa_texto),
    }


def _recursos(clave, nivel):
    base = {"matematica": "Material concreto, guía de ejercicios, pizarra", "lenguaje": "Texto escolar, textos de lectura, cuaderno",
            "ciencias": "Materiales de laboratorio o del entorno, guía de trabajo", "historia": "Fuentes, mapas, línea de tiempo"}
    extra = {"crear": ", pauta o rúbrica", "analizar": ", organizador gráfico", "evaluar": ", pauta de debate"}
    return base.get(clave, "Texto escolar, guía de trabajo, pizarra") + extra.get(nivel, "")


def indicadores(oa_texto):
    """Indicadores de evaluación sugeridos (lo observable que muestra el logro del OA)."""
    nivel = nivel_bloom(oa_texto)
    contenido = _contenido(oa_texto)
    corto = contenido if len(contenido) < 110 else contenido[:110].rsplit(" ", 1)[0] + "…"
    plantillas = {
        "recordar": ["Identifica {c}.", "Nombra ejemplos relacionados con lo trabajado."],
        "comprender": ["Explica con sus palabras {c}.", "Da ejemplos propios relacionados con el objetivo."],
        "aplicar": ["Aplica procedimientos para {c}.", "Resuelve problemas en contextos nuevos y verifica sus resultados."],
        "analizar": ["Analiza {c}, usando evidencia.", "Establece semejanzas, diferencias o relaciones de causa y efecto."],
        "evaluar": ["Evalúa {c}, con criterios explícitos.", "Fundamenta su postura con evidencia y considera otras visiones."],
        "crear": ["Produce un trabajo que muestra {c}.", "Revisa y mejora su producto a partir de la retroalimentación."],
    }
    return [p.format(c=corto) for p in plantillas[nivel]]


def _sumativa(oas_peso):
    """oas_peso: [(texto_oa, n° de clases)] → propuesta de evaluación sumativa con tabla de especificaciones."""
    niveles = Counter()
    for texto, peso in oas_peso:
        niveles[nivel_bloom(texto)] += peso
    principal = max(niveles, key=lambda n: (niveles[n], list(NIVELES_BLOOM).index(n) * -1))
    nombre, descripcion = SUMATIVAS[principal]
    total = sum(p for _, p in oas_peso) or 1
    tabla = []
    for texto, peso in oas_peso:
        pct = round(peso * 100 / total)
        tabla.append({"oa": texto, "porcentaje": pct, "nivel": NOMBRE_NIVEL[nivel_bloom(texto)],
                      "items": max(1, round(pct / 10))})
    return {"tipo": nombre, "descripcion": descripcion, "nivel": NOMBRE_NIVEL[principal],
            "tabla": tabla, "rubrica": CRITERIOS_RUBRICA[principal], "niveles_logro": NIVELES_LOGRO}


def evaluacion_de_unidad(ac, unidad=None):
    """Sugiere la evaluación sumativa de una unidad según lo planificado: OA trabajados y n° de clases de cada uno."""
    clases = ac.clases.prefetch_related("oas")
    if unidad:
        clases = clases.filter(unidad=unidad)
    conteo = OrderedDict()
    sin_oa = 0
    for c in clases.order_by("fecha", "id"):
        oas = list(c.oas.all())
        if not oas:
            sin_oa += 1
            if c.objetivo.strip():
                conteo[c.objetivo.strip()] = conteo.get(c.objetivo.strip(), 0) + 1
            continue
        for oa in oas:
            clave = str(oa)
            conteo[clave] = conteo.get(clave, 0) + 1
    if not conteo:
        return None
    propuesta = _sumativa(list(conteo.items()))
    propuesta["n_clases"] = clases.count()
    propuesta["sin_oa"] = sin_oa
    propuesta["unidad"] = unidad or "todas las unidades"
    niveles = {nivel_bloom(t) for t in conteo}
    propuesta["formativas"] = []
    vistos = set()
    for n in NIVELES_BLOOM:
        if n in niveles:
            for nombre, desc in FORMATIVAS[n][:2]:
                if nombre not in vistos:
                    vistos.add(nombre)
                    propuesta["formativas"].append({"nombre": nombre, "descripcion": desc})
    return propuesta
