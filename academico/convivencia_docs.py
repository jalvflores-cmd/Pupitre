"""Documentos tipo de Convivencia Educativa: protocolos de actuación, reglamento interno, PGCE y formatos.

Contenido redactado como modelo a partir de la normativa chilena vigente (Ley General de Educación, Ley 20.536 sobre
violencia escolar, Ley 21.128 Aula Segura, Ley 21.430 de Garantías de la Niñez, Ley 21.545 de Autismo, Ley 21.809
sobre convivencia, buen trato y bienestar de las comunidades educativas, y circulares de la Superintendencia de
Educación). Cada establecimiento debe revisarlo, ajustarlo a su realidad y aprobarlo según su procedimiento interno.
Los textos se generan en Word (.docx) para que puedan editarse.
"""
from io import BytesIO

NOTA_REVISION = (
    "Documento tipo generado por Pupitre como base de trabajo. Las referencias normativas y los plazos fueron "
    "redactados a partir de la normativa vigente y de formatos de referencia, y deben contrastarse con los textos "
    "oficiales (bcn.cl, supereduc.cl, convivenciaparaciudadania.mineduc.cl) y con las orientaciones del sostenedor "
    "antes de aprobarse e incorporarse al Reglamento Interno.")

NORMATIVA_BASE = [
    "Ley N° 20.370, General de Educación (DFL N° 2 de 2009, Mineduc).",
    "Ley N° 20.536, sobre Violencia Escolar.",
    "Ley N° 21.809, sobre convivencia, buen trato y bienestar de las comunidades educativas (vigente desde el 1 de julio de 2026).",
    "Ley N° 21.430, sobre Garantías y Protección Integral de los Derechos de la Niñez y Adolescencia.",
    "Circular N° 482 de 2018 de la Superintendencia de Educación, sobre Reglamentos Internos de establecimientos de enseñanza básica y media.",
    "Política Nacional de Convivencia Educativa 2024-2030 (Mineduc).",
]

PRINCIPIOS = [
    "Interés superior del niño, niña y adolescente: toda decisión prioriza su protección y bienestar.",
    "No revictimización: se evita repetir entrevistas sobre los hechos; se privilegia un relato único y se deriva a las instituciones competentes (Ley 21.057).",
    "Confidencialidad: los antecedentes se manejan con reserva y solo por quienes intervienen en el procedimiento.",
    "Justo y racional procedimiento: presunción de inocencia, derecho a ser oído, a presentar antecedentes y a apelar.",
    "Proporcionalidad y gradualidad de las medidas, privilegiando las de carácter formativo, pedagógico y reparatorio.",
    "Enfoque de derechos, de género e inclusión, con ajustes razonables cuando corresponda.",
    "Registro y trazabilidad: toda actuación queda registrada por escrito (actas, entrevistas, informes).",
]

# Cada protocolo: pasos = [(etapa, plazo, responsable, [acciones])]
DOCUMENTOS = [
    {
        "clave": "desregulacion", "tipo": "protocolo", "protocolo": "DESREGULACION",
        "titulo": "Protocolo de actuación frente a desregulación emocional y conductual (DEC), con énfasis en estudiantes TEA",
        "resumen": "Regula la prevención, el abordaje y el seguimiento de episodios de desregulación emocional y conductual de "
                   "cualquier estudiante, con o sin diagnóstico, y en particular de estudiantes en el espectro autista, "
                   "incluyendo el Plan de Acompañamiento Emocional y Conductual (PAEC) y la bitácora de registro.",
        "normativa": [
            "Ley N° 21.545, que establece la promoción de la inclusión, la atención integral y la protección de los derechos de las personas con trastorno del espectro autista (2023).",
            "Circular de la Superintendencia de Educación aprobada por Resolución Exenta N° 586 de 2023, sobre inclusión, atención integral y protección de los derechos de párvulos y estudiantes con TEA.",
            "Ordinario N° 222 de 2024 de la Superintendencia de Educación, sobre contención física en casos de desregulación emocional y conductual.",
            "Decreto N° 170 de 2009 y Decreto N° 83 de 2015 (Mineduc), sobre necesidades educativas especiales y diversificación de la enseñanza.",
        ],
        "secciones": [
            ("Definiciones", [
                "Desregulación emocional y conductual (DEC): reacción motora y emocional ante uno o varios estímulos o situaciones desencadenantes que, por su frecuencia, duración o intensidad, requiere la atención específica de una persona adulta, ya que el o la estudiante no logra autorregularse.",
                "Plan de Acompañamiento Emocional y Conductual (PAEC): plan individual que caracteriza al estudiante, sus gatillantes, señales de alerta, estrategias que le ayudan y los roles del equipo de aula. Es obligatorio para estudiantes con diagnóstico TEA y recomendable para todo estudiante con episodios reiterados.",
                "Bitácora de registro: registro de cada episodio (fecha, contexto, gatillantes, duración, acciones, resultado) que permite ajustar el PAEC.",
                "Contención física (restricción de movimiento tutelada): último recurso, solo ante riesgo inminente para el estudiante o terceros, por adultos capacitados, por el menor tiempo posible y nunca como castigo.",
            ]),
            ("Medidas preventivas", [
                "- Identificar oportunamente a los estudiantes que requieren un plan preventivo (con o sin diagnóstico) y elaborar su PAEC junto a la familia, profesor(a) jefe, equipo PIE y convivencia.",
                "- Anticipar cambios de rutina con apoyos visuales (horarios, pictogramas, claves visuales) y cuidar las transiciones entre actividades.",
                "- Disponer de un espacio de calma o regulación y de materiales sensoriales.",
                "- Capacitar al equipo en manejo de DEC y en el Enfoque Escuela Total; contar con un plan de autocuidado para el equipo.",
                "- Mantener actualizados los datos de contacto del apoderado(a) y del centro de salud del estudiante.",
            ]),
            ("Fases de la desregulación y respuesta esperada", [
                "Fase 1, inicial: señales de sobrecarga (tensión, inquietud, frustración). Aplicar las estrategias del PAEC: ofrecer pausa, cambiar de actividad, reducir estímulos, usar el canal de comunicación preferido.",
                "Fase 2, aumento: el estudiante no responde a la comunicación verbal y aumenta la agitación. Acompañar sin invadir, retirar objetos de riesgo, despejar el espacio, hablar poco y en tono calmado, trasladar al grupo si es necesario.",
                "Fase 3, descontrol con riesgo: solo si hay riesgo inminente para sí o terceros, realizar contención física por personal capacitado, informar de inmediato a la familia y dejar registro detallado.",
            ]),
            ("Roles durante el episodio", [
                "- Encargado(a): adulto con mejor vínculo con el estudiante (definido en el PAEC); acompaña y guía la regulación.",
                "- Acompañante interno: apoya al encargado(a), evalúa riesgos del entorno y resguarda al resto del curso.",
                "- Acompañante externo: coordina, avisa a dirección y convivencia, y contacta al apoderado(a).",
            ]),
        ],
        "pasos": [
            ("Detección y PAEC", "Al inicio del año o al detectar la necesidad", "Profesor(a) jefe, PIE y Encargado(a) de convivencia",
             ["Identificar a los estudiantes que requieren apoyos.", "Elaborar o actualizar el PAEC con la familia y el equipo de aula.",
              "Si se observan señales compatibles con TEA sin diagnóstico, informar a la familia y derivar al centro de salud con el formulario de derivación."]),
            ("Abordaje del episodio", "Inmediato", "Adulto a cargo y equipo definido en el PAEC",
             ["Aplicar las estrategias según la fase.", "Resguardar al estudiante y al resto del curso.", "Contención física solo como último recurso ante riesgo inminente."]),
            ("Aviso a la familia", "El mismo día (de inmediato si hubo contención física o lesiones)", "Acompañante externo o Encargado(a) de convivencia",
             ["Informar al apoderado(a) lo ocurrido y las acciones realizadas.", "Si se requiere, solicitar que concurra al establecimiento (sin que esto implique una reducción de jornada no acordada)."]),
            ("Registro", "Dentro de 24 horas", "Encargado(a) del episodio",
             ["Completar la bitácora de registro.", "Si hubo lesiones, activar el protocolo de accidente escolar."]),
            ("Reparación y ajuste del PAEC", "Dentro de 5 días hábiles", "Encargado(a) de convivencia, PIE y profesor(a) jefe",
             ["Conversación de reparación con el estudiante cuando esté regulado.", "Revisar gatillantes y ajustar el PAEC con la familia.",
              "Evaluar acciones con el curso y apoyo al equipo."]),
            ("Seguimiento", "Mensual mientras se mantengan los episodios", "Encargado(a) de convivencia",
             ["Revisar la bitácora y la efectividad del PAEC.", "Coordinar con salud y redes de apoyo cuando corresponda."]),
        ],
    },
    {
        "clave": "maltrato-estudiantes", "tipo": "protocolo", "protocolo": "MALTRATO_ESTUDIANTES",
        "titulo": "Protocolo de actuación frente a maltrato, acoso escolar o violencia entre estudiantes",
        "resumen": "Establece cómo se reciben, investigan y resuelven las situaciones de maltrato, acoso escolar (bullying), "
                   "ciberacoso o violencia entre estudiantes, con medidas formativas, de apoyo y reparatorias.",
        "normativa": ["Ley N° 20.536, sobre Violencia Escolar (art. 16 A a 16 E de la LGE).",
                      "Ley N° 21.128, Aula Segura, para hechos que afecten gravemente la convivencia."],
        "secciones": [
            ("Definiciones", [
                "Maltrato escolar: toda acción u omisión, intencional, física o psicológica, realizada en forma escrita, verbal o a través de medios tecnológicos, que afecte a un estudiante.",
                "Acoso escolar: agresión u hostigamiento reiterado, realizado fuera o dentro del establecimiento, por estudiantes que en forma individual o colectiva atenten contra otro, valiéndose de una situación de superioridad o de indefensión del afectado, que le provoque maltrato, humillación o temor fundado de verse expuesto a un mal de carácter grave (art. 16 B LGE).",
            ]),
        ],
        "pasos": [
            ("Recepción de la denuncia", "Inmediato", "Cualquier funcionario(a) que tome conocimiento",
             ["Acoger el relato sin juzgar y resguardar la integridad de los involucrados.", "Informar el mismo día al Encargado(a) de convivencia, quien registra la activación."]),
            ("Medidas de resguardo", "Dentro de 24 horas", "Encargado(a) de convivencia e Inspectoría",
             ["Separar espacios o adecuar rutinas si hay riesgo.", "Informar a los apoderados de los estudiantes involucrados.",
              "Si hay lesiones, activar el protocolo de accidente escolar; si hay delito, denunciar dentro de 24 horas (art. 175 y 176 del Código Procesal Penal)."]),
            ("Indagación", "Hasta 10 días hábiles (prorrogables con fundamento)", "Encargado(a) de convivencia",
             ["Entrevistar a los involucrados y testigos, resguardando su identidad.", "Recopilar antecedentes y dejar actas firmadas.",
              "Garantizar el derecho de las partes a ser oídas y presentar descargos."]),
            ("Resolución", "Dentro de 5 días hábiles desde el cierre de la indagación", "Dirección, con informe de Convivencia",
             ["Determinar si se acreditan los hechos y aplicar las medidas del Reglamento Interno (formativas, reparatorias o disciplinarias).",
              "Notificar por escrito a los apoderados, indicando el derecho a apelar."]),
            ("Apelación", "5 días hábiles desde la notificación", "Dirección (resuelve con consulta al Consejo de Profesores cuando corresponda)",
             ["Recibir la apelación por escrito y responder fundadamente."]),
            ("Seguimiento y cierre", "Hasta 30 días después de la resolución", "Encargado(a) de convivencia y profesor(a) jefe",
             ["Verificar el cumplimiento de medidas y el bienestar de la víctima.", "Trabajo formativo con el curso.", "Cerrar el protocolo con un informe."]),
        ],
    },
    {
        "clave": "maltrato-adulto", "tipo": "protocolo", "protocolo": "MALTRATO_ADULTO",
        "titulo": "Protocolo de actuación frente a maltrato de un adulto a un estudiante",
        "resumen": "Regula la actuación cuando un funcionario(a), apoderado(a) u otro adulto de la comunidad educativa "
                   "ejerce maltrato físico o psicológico contra un estudiante.",
        "normativa": ["Art. 16 D de la LGE: reviste especial gravedad la violencia ejercida por un adulto de la comunidad educativa contra un estudiante.",
                      "Código Procesal Penal, art. 175 y 176 (obligación de denunciar).", "Código del Trabajo y Estatuto Docente, para medidas respecto de funcionarios."],
        "secciones": [],
        "pasos": [
            ("Recepción y resguardo", "Inmediato", "Quien toma conocimiento; Dirección",
             ["Proteger al estudiante y separarlo del adulto involucrado.", "Informar a Dirección y al Encargado(a) de convivencia el mismo día.",
              "Si es funcionario(a), Dirección evalúa medidas de resguardo (cambio de funciones), sin afectar la presunción de inocencia."]),
            ("Aviso a la familia y denuncia", "Dentro de 24 horas", "Dirección",
             ["Informar al apoderado(a) del estudiante.", "Si los hechos pueden constituir delito, denunciar a Fiscalía, Carabineros o PDI.",
              "Si hay lesiones, activar el protocolo de accidente escolar y constatar lesiones."]),
            ("Investigación", "Hasta 10 días hábiles", "Encargado(a) de convivencia o quien designe Dirección",
             ["Recabar antecedentes y escuchar al adulto involucrado.", "Si es funcionario(a), aplicar además el procedimiento laboral o sumario que corresponda."]),
            ("Resolución y medidas", "5 días hábiles", "Dirección / Sostenedor",
             ["Adoptar las medidas que correspondan (cambio de apoderado, medidas laborales, apoyo psicosocial al estudiante).", "Notificar a las partes e informar el derecho a apelar."]),
            ("Seguimiento", "30 días", "Encargado(a) de convivencia", ["Acompañar al estudiante y verificar el cumplimiento de las medidas."]),
        ],
    },
    {
        "clave": "vulneracion", "tipo": "protocolo", "protocolo": "VULNERACION",
        "titulo": "Protocolo de actuación frente a vulneración de derechos de estudiantes",
        "resumen": "Aborda situaciones de negligencia, descuido, abandono, inasistencia injustificada reiterada, falta de "
                   "atención de salud u otras vulneraciones de derechos que afecten a un estudiante.",
        "normativa": ["Ley N° 21.430, de Garantías de la Niñez (Oficinas Locales de la Niñez).", "Ley N° 19.968, que crea los Tribunales de Familia."],
        "secciones": [],
        "pasos": [
            ("Detección", "Inmediato", "Cualquier funcionario(a)", ["Informar al Encargado(a) de convivencia, quien registra la activación."]),
            ("Recopilación de antecedentes", "Hasta 5 días hábiles", "Encargado(a) de convivencia y dupla psicosocial",
             ["Entrevista con el apoderado(a) (no indagar los hechos con el estudiante).", "Revisar asistencia, registros y antecedentes de salud."]),
            ("Derivación", "Dentro de 48 horas desde que se confirma la sospecha", "Encargado(a) de convivencia",
             ["Derivar a la Oficina Local de la Niñez (OLN) o a la red pertinente.", "Si hay riesgo grave, solicitar medida de protección al Tribunal de Familia; si hay delito, denunciar dentro de 24 horas."]),
            ("Apoyo pedagógico y psicosocial", "Mientras dure la situación", "Profesor(a) jefe, UTP y dupla psicosocial",
             ["Plan de acompañamiento del estudiante.", "Seguimiento con la familia y la red."]),
            ("Cierre", "Al finalizar la intervención", "Encargado(a) de convivencia", ["Informe de cierre con las acciones realizadas."]),
        ],
    },
    {
        "clave": "abuso-sexual", "tipo": "protocolo", "protocolo": "ABUSO_SEXUAL",
        "titulo": "Protocolo de actuación frente a agresiones sexuales y hechos de connotación sexual",
        "resumen": "Define la actuación inmediata ante la sospecha o develación de agresiones sexuales o hechos de connotación "
                   "sexual que afecten a estudiantes, evitando la revictimización.",
        "normativa": ["Código Procesal Penal, art. 175 y 176: obligación de denunciar dentro de 24 horas.",
                      "Ley N° 21.057, que regula entrevistas grabadas en video para evitar la revictimización.",
                      "Ley N° 21.675, sobre violencia contra las mujeres en razón de género."],
        "secciones": [("Orientaciones esenciales", [
            "- Escuchar con calma y sin interrogar; no pedir detalles ni que repita el relato; registrar textualmente lo que el estudiante dijo.",
            "- No confrontar al estudiante con el presunto agresor ni informar a éste.",
            "- No investigar los hechos: eso corresponde a Fiscalía; el establecimiento resguarda y denuncia.",
        ])],
        "pasos": [
            ("Acogida y resguardo", "Inmediato", "Quien recibe la develación",
             ["Acoger, contener y resguardar al estudiante.", "Informar de inmediato a Dirección y al Encargado(a) de convivencia."]),
            ("Denuncia", "Dentro de 24 horas", "Dirección (o quien recibió el relato)",
             ["Denunciar a Fiscalía, Carabineros o PDI.", "Si es necesario, solicitar medida de protección al Tribunal de Familia."]),
            ("Aviso a la familia", "El mismo día", "Dirección o Encargado(a) de convivencia",
             ["Informar a un adulto protector (si el presunto agresor es familiar, informar a otro adulto responsable)."]),
            ("Medidas de protección", "Inmediato", "Dirección",
             ["Si el involucrado es funcionario(a), separarlo de funciones con contacto con estudiantes mientras dure la investigación.",
              "Si es otro estudiante, aplicar medidas de resguardo para ambos, considerando que ambos son sujetos de protección."]),
            ("Acompañamiento y seguimiento", "Mientras dure el proceso", "Dupla psicosocial y profesor(a) jefe",
             ["Apoyo pedagógico y psicosocial.", "Coordinación con la red y colaboración con la investigación."]),
        ],
    },
    {
        "clave": "autolesion", "tipo": "protocolo", "protocolo": "AUTOLESION",
        "titulo": "Protocolo de actuación frente a conducta autolesiva o riesgo suicida",
        "resumen": "Orienta la detección, primera respuesta, derivación a salud y acompañamiento de estudiantes con ideación, "
                   "conducta autolesiva o intento suicida, y la postvención en la comunidad.",
        "normativa": ["Recomendaciones para la prevención de la conducta suicida en establecimientos educacionales (Mineduc - Minsal, 2019).",
                      "Ley N° 21.331, de reconocimiento y protección de los derechos de las personas en la atención de salud mental."],
        "secciones": [],
        "pasos": [
            ("Primera respuesta", "Inmediato", "Quien detecta la situación",
             ["Mantener la calma, no dejar solo al estudiante y escuchar sin juzgar.", "Informar de inmediato al Encargado(a) de convivencia o dupla psicosocial."]),
            ("Evaluación del riesgo", "El mismo día", "Dupla psicosocial o Encargado(a) de convivencia",
             ["Aplicar una pauta de evaluación de riesgo (p. ej. Columbia).", "Si hay riesgo inminente o intento: llamar al SAMU (131) o trasladar a urgencia, avisando a la familia."]),
            ("Aviso a la familia y derivación", "El mismo día", "Encargado(a) de convivencia",
             ["Citar al apoderado(a), informar y entregar ficha de derivación al centro de salud (CESFAM o salud mental).", "Dejar acta firmada."]),
            ("Plan de acompañamiento", "Dentro de 5 días hábiles", "Dupla psicosocial, profesor(a) jefe y UTP",
             ["Acordar apoyos y, si corresponde, ajustes académicos.", "Coordinación con el tratante."]),
            ("Seguimiento y postvención", "Según el caso", "Equipo de convivencia",
             ["Seguimiento periódico con el estudiante y la familia.", "En caso de suicidio consumado, aplicar acciones de postvención con el curso y la comunidad."]),
        ],
    },
    {
        "clave": "drogas-alcohol", "tipo": "protocolo", "protocolo": "DROGAS_ALCOHOL",
        "titulo": "Protocolo de actuación frente a consumo, porte o tráfico de alcohol y drogas",
        "resumen": "Establece la actuación ante sospecha o evidencia de consumo, porte o microtráfico de alcohol o drogas, "
                   "priorizando la prevención y la derivación a la red de apoyo.",
        "normativa": ["Ley N° 20.000, que sanciona el tráfico ilícito de estupefacientes.", "Ley N° 19.925, sobre expendio y consumo de bebidas alcohólicas.",
                      "Programas preventivos de SENDA."],
        "secciones": [],
        "pasos": [
            ("Detección", "Inmediato", "Cualquier funcionario(a)", ["Resguardar al estudiante y avisar al Encargado(a) de convivencia e Inspectoría."]),
            ("Atención y aviso", "El mismo día", "Inspectoría y Encargado(a) de convivencia",
             ["Si el estudiante está bajo los efectos, procurar atención de salud.", "Citar al apoderado(a) y dejar acta."]),
            ("Denuncia", "Dentro de 24 horas", "Dirección", ["Ante porte o tráfico, denunciar a Carabineros, PDI o Fiscalía (no se realizan registros a las pertenencias)."]),
            ("Medidas formativas y derivación", "Dentro de 5 días hábiles", "Encargado(a) de convivencia",
             ["Aplicar medidas del Reglamento Interno.", "Derivar a SENDA Previene, CESFAM u otra red."]),
            ("Seguimiento", "30 días o más", "Dupla psicosocial", ["Monitorear la adherencia a la intervención y el bienestar del estudiante."]),
        ],
    },
    {
        "clave": "accidente", "tipo": "protocolo", "protocolo": "ACCIDENTE",
        "titulo": "Protocolo de actuación frente a accidentes escolares",
        "resumen": "Regula la atención de accidentes ocurridos durante la jornada, actividades o trayecto, y el uso del seguro escolar.",
        "normativa": ["Ley N° 16.744 y Decreto Supremo N° 313 de 1972, que incluye a los estudiantes en el seguro de accidentes escolares."],
        "secciones": [],
        "pasos": [
            ("Primera atención", "Inmediato", "Adulto más cercano; encargado(a) de primeros auxilios",
             ["Evaluar la gravedad y prestar primeros auxilios.", "No mover al estudiante si se sospecha lesión grave."]),
            ("Aviso a la familia", "Inmediato", "Inspectoría", ["Comunicar al apoderado(a) lo ocurrido y las acciones."]),
            ("Traslado (si corresponde)", "Inmediato en accidente grave", "Inspectoría",
             ["Llamar al SAMU (131) o trasladar al servicio de urgencia público con el formulario de Declaración Individual de Accidente Escolar.",
              "Un funcionario(a) acompaña al estudiante hasta que llegue el apoderado(a)."]),
            ("Registro", "El mismo día", "Inspectoría", ["Completar el formulario del seguro escolar y registrar el accidente."]),
            ("Seguimiento", "Días siguientes", "Profesor(a) jefe", ["Consultar por la recuperación y coordinar apoyos pedagógicos si hay ausencias."]),
        ],
    },
    {
        "clave": "embarazo", "tipo": "protocolo", "protocolo": "EMBARAZO",
        "titulo": "Protocolo de retención y apoyo a estudiantes embarazadas, madres y padres",
        "resumen": "Asegura el derecho a la educación de estudiantes embarazadas, madres y padres, con facilidades académicas y administrativas.",
        "normativa": ["Art. 11 de la LGE: el embarazo y la maternidad no constituyen impedimento para ingresar y permanecer en el establecimiento.",
                      "Decreto N° 79 de 2004 (Mineduc), que regula el estatuto de las alumnas en situación de embarazo y maternidad.",
                      "Circular de la Superintendencia de Educación sobre estudiantes embarazadas, madres y padres (Res. Ex. N° 193 de 2018)."],
        "secciones": [],
        "pasos": [
            ("Comunicación de la situación", "Al conocerse", "Profesor(a) jefe / Encargado(a) de convivencia", ["Acoger y orientar a la o el estudiante y su familia; designar un tutor(a)."]),
            ("Plan académico flexible", "Dentro de 10 días hábiles", "UTP",
             ["Calendario de evaluaciones flexible y apoyos pedagógicos.", "Criterios de promoción con asistencia menor a 85 % cuando las inasistencias se deban al embarazo, parto o control del niño(a)."]),
            ("Facilidades administrativas", "Durante el embarazo y la lactancia", "Inspectoría",
             ["Permisos para controles médicos, horario de lactancia y salidas al baño.", "Adecuación del uniforme y de las clases de Educación Física."]),
            ("Seguimiento", "Mensual", "Tutor(a)", ["Monitorear asistencia y rendimiento; coordinar con redes (CESFAM, JUNAEB)."]),
        ],
    },
    {
        "clave": "identidad-genero", "tipo": "protocolo", "protocolo": "",
        "titulo": "Protocolo de reconocimiento de la identidad de género de estudiantes trans",
        "resumen": "Establece el procedimiento para el reconocimiento del nombre social y las medidas de apoyo a estudiantes trans.",
        "normativa": ["Ley N° 21.120, que reconoce y da protección al derecho a la identidad de género.",
                      "Circular de la Superintendencia de Educación sobre derechos de niñas, niños y estudiantes trans (Res. Ex. N° 812 de 2021)."],
        "secciones": [],
        "pasos": [
            ("Solicitud", "Al recibirla", "Dirección", ["El apoderado(a), o el estudiante mayor de 14 años, solicita entrevista con Dirección."]),
            ("Entrevista y acuerdos", "Dentro de 5 días hábiles", "Dirección y Encargado(a) de convivencia",
             ["Registrar en acta los acuerdos: nombre social, uso de uniforme, baños y camarines, apoyo a la familia."]),
            ("Implementación", "Inmediato tras el acuerdo", "Dirección, UTP e Inspectoría",
             ["Usar el nombre social en registros internos (el nombre legal se mantiene en documentos oficiales hasta su cambio).", "Informar al equipo docente con la debida reserva."]),
            ("Seguimiento", "Semestral", "Encargado(a) de convivencia", ["Revisar el bienestar del estudiante y la aplicación de los acuerdos."]),
        ],
    },
    {
        "clave": "aula-segura", "tipo": "protocolo", "protocolo": "AULA_SEGURA",
        "titulo": "Procedimiento de expulsión o cancelación de matrícula (Ley Aula Segura)",
        "resumen": "Regula el procedimiento sancionatorio ante faltas gravísimas que afecten gravemente la convivencia escolar, "
                   "con la medida cautelar de suspensión y el debido proceso.",
        "normativa": ["Ley N° 21.128, Aula Segura, que modifica el art. 6 del DFL N° 2 de 1998 (Ley de Subvenciones).", "Art. 10 y 46 de la LGE."],
        "secciones": [],
        "pasos": [
            ("Inicio del procedimiento", "Al conocer los hechos", "Dirección",
             ["Notificar por escrito al estudiante y al apoderado(a) el inicio del procedimiento.", "Puede suspender como medida cautelar mientras dura el procedimiento."]),
            ("Descargos", "5 días hábiles", "Estudiante y apoderado(a)", ["Presentar descargos y medios de prueba."]),
            ("Resolución", "10 días hábiles desde la notificación de la medida cautelar", "Dirección", ["Resolver fundadamente y notificar por escrito."]),
            ("Reconsideración", "5 días hábiles desde la notificación", "Dirección, previa consulta al Consejo de Profesores",
             ["Resolver la solicitud de reconsideración."]),
            ("Informe a la Superintendencia", "5 días hábiles desde que la medida queda firme", "Dirección",
             ["Informar a la Superintendencia de Educación para que revise el cumplimiento del procedimiento."]),
        ],
    },
    {
        "clave": "maltrato-funcionario", "tipo": "protocolo", "protocolo": "MALTRATO_A_FUNCIONARIO",
        "titulo": "Protocolo de actuación frente a maltrato entre adultos y hacia funcionarios(as)",
        "resumen": "Aborda situaciones de maltrato o violencia de apoderados u otros adultos hacia funcionarios(as), y entre adultos de la comunidad.",
        "normativa": ["Ley N° 21.809, sobre convivencia, buen trato y bienestar de las comunidades educativas.",
                      "Ley N° 21.643 (Ley Karin), para situaciones de acoso laboral, acoso sexual o violencia en el trabajo entre funcionarios(as)."],
        "secciones": [],
        "pasos": [
            ("Recepción", "Inmediato", "Dirección o Encargado(a) de convivencia", ["Acoger al afectado(a) y registrar los hechos."]),
            ("Resguardo y denuncia", "Dentro de 24 horas", "Dirección",
             ["Adoptar medidas de resguardo.", "Si hay agresión física o amenazas graves, denunciar.", "Entre funcionarios, aplicar el procedimiento de la Ley Karin."]),
            ("Mediación o medidas", "Hasta 10 días hábiles", "Encargado(a) de convivencia",
             ["Ofrecer mediación cuando sea pertinente.", "Aplicar medidas del Reglamento Interno (p. ej. cambio de apoderado)."]),
            ("Cierre", "Al resolver", "Dirección", ["Informar a las partes y registrar el cierre."]),
        ],
    },
    {
        "clave": "reclamos", "tipo": "protocolo", "protocolo": "",
        "titulo": "Conducto regular y procedimiento de atención de solicitudes y reclamos",
        "resumen": "Define las instancias y plazos para atender consultas, solicitudes, reclamos y denuncias de la comunidad "
                   "educativa, promoviendo la resolución temprana de los conflictos (Ley 21.809).",
        "normativa": ["Ley N° 21.809, sobre convivencia, buen trato y bienestar de las comunidades educativas.",
                      "Ley N° 20.529, Sistema de Aseguramiento de la Calidad (denuncias ante la Superintendencia de Educación)."],
        "secciones": [("Instancias del conducto regular", [
            "1. Profesor(a) de asignatura o profesor(a) jefe: materias pedagógicas y de convivencia cotidiana del curso.",
            "2. Encargado(a) de convivencia, Inspectoría General o UTP, según la materia.",
            "3. Dirección del establecimiento.",
            "4. Sostenedor (o Servicio Local de Educación Pública).",
            "5. Superintendencia de Educación, cuando la situación no se resuelve en el establecimiento.",
        ])],
        "pasos": [
            ("Recepción", "Al presentarse", "Funcionario(a) de la instancia que corresponda",
             ["Recibir en privado, informar alcance, confidencialidad y obligación de denunciar cuando corresponda.", "Levantar acta firmada por ambas partes."]),
            ("Gestión", "Hasta 5 días hábiles", "Instancia responsable", ["Analizar, reunir antecedentes y, si corresponde, activar el protocolo específico."]),
            ("Respuesta", "Hasta 10 días hábiles", "Instancia responsable o Dirección", ["Responder por escrito al requirente."]),
            ("Escalamiento", "Si no hay respuesta o acuerdo", "Requirente", ["Recurrir a la instancia siguiente del conducto regular."]),
        ],
    },
    {
        "clave": "inasistencia", "tipo": "protocolo", "protocolo": "",
        "titulo": "Procedimiento de seguimiento de inasistencias y baja de matrícula por ausencia prolongada",
        "resumen": "Regula las alertas tempranas ante inasistencias y el procedimiento mínimo para dar de baja la matrícula "
                   "por inasistencia injustificada prolongada, resguardando la trayectoria educativa.",
        "normativa": ["Circular N° 30 de 2021 de la Superintendencia de Educación, modificada por Resolución Exenta N° 432 de 2023, sobre registros de matrícula y asistencia."],
        "secciones": [],
        "pasos": [
            ("Alerta temprana", "3 a 5 días de inasistencia", "Profesor(a) jefe", ["Contactar al apoderado(a) e identificar causas."]),
            ("Alerta intermedia", "6 a 10 días hábiles", "Dupla psicosocial", ["Contacto telefónico formal, registro en acta y derivación a convivencia."]),
            ("Alerta avanzada", "11 a 19 días hábiles", "Encargado(a) de convivencia",
             ["Entrevista con el apoderado(a), apoyo pedagógico y psicosocial, plan de acompañamiento.", "Evaluar activación del protocolo de vulneración de derechos."]),
            ("Procedimiento de baja", "Desde 40 días hábiles de inasistencia continua injustificada", "Dirección",
             ["Contacto telefónico, luego correo o carta certificada y al menos una visita domiciliaria.",
              "Si el apoderado es ubicable y no justifica: activar vulneración de derechos.", "Si no es ubicable: informe fundado validado por Dirección y baja en el registro."]),
        ],
    },
]

_CORTOS = {
    "desregulacion": "Desregulación emocional (TEA)", "maltrato-estudiantes": "Maltrato o acoso entre estudiantes",
    "maltrato-adulto": "Maltrato de adulto a estudiante", "vulneracion": "Vulneración de derechos",
    "abuso-sexual": "Agresión o connotación sexual", "autolesion": "Autolesión o riesgo suicida",
    "drogas-alcohol": "Alcohol y drogas", "accidente": "Accidente escolar", "embarazo": "Embarazo, maternidad y paternidad",
    "identidad-genero": "Identidad de género", "aula-segura": "Aula Segura", "maltrato-funcionario": "Maltrato a funcionarios",
    "reclamos": "Reclamos y conducto regular", "inasistencia": "Inasistencia reiterada",
}
for _d in DOCUMENTOS:
    _d["corto"] = _CORTOS.get(_d["clave"], _d["titulo"])

PROTOCOLOS = [d for d in DOCUMENTOS if d["tipo"] == "protocolo"]
POR_CLAVE = {d["clave"]: d for d in DOCUMENTOS}
POR_PROTOCOLO = {d["protocolo"]: d for d in DOCUMENTOS if d.get("protocolo")}

NORMATIVA_TIPO = [
    {"clave": "reglamento-interno", "titulo": "Reglamento Interno de Convivencia Escolar (estructura tipo)",
     "resumen": "Índice y contenidos mínimos del Reglamento Interno para enseñanza básica y media según la Circular N° 482 "
                "de 2018 y la Ley 21.809, con los protocolos de Pupitre como anexos."},
    {"clave": "pgce", "titulo": "Plan de Gestión de la Convivencia Educativa (PGCE)",
     "resumen": "Estructura del PGCE alineada con la PNCE 2024-2030 y el Enfoque Escuela Total, con la articulación con las "
                "acciones del PME de la dimensión Convivencia ya registradas en Pupitre."},
]
FORMATOS = [
    {"clave": "acta-activacion", "titulo": "Acta de activación de protocolo",
     "resumen": "Registro de la activación: hechos, involucrados, medidas de resguardo y responsables."},
    {"clave": "paec", "titulo": "Plan de Acompañamiento Emocional y Conductual (PAEC) y bitácora",
     "resumen": "Formato del PAEC para estudiantes con desregulación emocional y conductual (obligatorio para estudiantes TEA)."},
    {"clave": "derivacion", "titulo": "Ficha de derivación a red de apoyo",
     "resumen": "Derivación a OLN, CESFAM, SENDA u otra red, con los antecedentes mínimos."},
    {"clave": "carta-compromiso", "titulo": "Carta de compromiso",
     "resumen": "Acuerdos del estudiante y su familia con el establecimiento, con plazos y seguimiento."},
    {"clave": "informe-cierre", "titulo": "Informe de cierre de protocolo",
     "resumen": "Síntesis de las acciones realizadas, medidas aplicadas, resultados y seguimiento."},
]
TODOS = {d["clave"]: d for d in DOCUMENTOS + NORMATIVA_TIPO + FORMATOS}


# ---------------------------------------------------------------------------------------------- generación Word

def _datos(est):
    return {"Establecimiento": est.nombre, "RBD": est.rbd, "Dirección": " ".join(x for x in (est.direccion, est.comuna) if x),
            "Director(a)": est.director, "Región": est.region}


def _encabezado(doc, est, titulo):
    from docx.shared import Pt

    p = doc.add_paragraph()
    r = p.add_run(est.nombre.upper())
    r.bold, r.font.size = True, Pt(9)
    if est.rbd:
        p.add_run(f"  ·  RBD {est.rbd}").font.size = Pt(9)
    doc.add_heading(titulo, level=0)


def _tabla(doc, filas, encabezado=None, anchos=None):
    from docx.shared import Cm

    tabla = doc.add_table(rows=0, cols=len(filas[0] if filas else encabezado))
    tabla.style = "Table Grid"
    if encabezado:
        celdas = tabla.add_row().cells
        for c, t in zip(celdas, encabezado):
            c.text = ""
            c.paragraphs[0].add_run(t).bold = True
    for fila in filas:
        celdas = tabla.add_row().cells
        for c, t in zip(celdas, fila):
            c.text = str(t or "")
    if anchos:
        for fila in tabla.rows:
            for c, a in zip(fila.cells, anchos):
                c.width = Cm(a)
    doc.add_paragraph()
    return tabla


def _parrafos(doc, lineas):
    for linea in lineas:
        if linea.startswith("- "):
            doc.add_paragraph(linea[2:], style="List Bullet")
        else:
            doc.add_paragraph(linea)


def _cierre(doc, firmas=("Encargado(a) de Convivencia", "Director(a)")):
    doc.add_paragraph()
    _tabla(doc, [["\n\n\n" + f for f in firmas]])
    p = doc.add_paragraph()
    r = p.add_run(NOTA_REVISION)
    r.italic = True


def _protocolo(doc, est, d):
    _encabezado(doc, est, d["titulo"])
    doc.add_heading("I. Objetivo y alcance", level=1)
    doc.add_paragraph(d["resumen"])
    doc.add_paragraph("Este protocolo forma parte del Reglamento Interno y es conocido por toda la comunidad educativa. Su "
                      "activación no requiere una denuncia formal: basta que un funcionario(a) tome conocimiento de la situación.")
    doc.add_heading("II. Marco normativo", level=1)
    _parrafos(doc, ["- " + n for n in d["normativa"] + NORMATIVA_BASE])
    doc.add_heading("III. Principios", level=1)
    _parrafos(doc, ["- " + p for p in PRINCIPIOS])
    for i, (titulo, lineas) in enumerate(d["secciones"], start=4):
        doc.add_heading(f"{_romano(i)}. {titulo}", level=1)
        _parrafos(doc, lineas)
    n = 4 + len(d["secciones"])
    doc.add_heading(f"{_romano(n)}. Procedimiento, plazos y responsables", level=1)
    _tabla(doc, [[f"{i}. {e}", plazo, resp, "\n".join("• " + a for a in acciones)]
                 for i, (e, plazo, resp, acciones) in enumerate(d["pasos"], 1)],
           encabezado=["Etapa", "Plazo", "Responsable", "Acciones"], anchos=(3.5, 3, 3.5, 7))
    doc.add_heading(f"{_romano(n + 1)}. Registro, comunicación y cierre", level=1)
    _parrafos(doc, [
        "- Toda actuación se registra por escrito (acta de activación, entrevistas firmadas, informes) y se resguarda con acceso restringido. En Pupitre, la activación se registra en la anotación derivada y las entrevistas en la ficha del estudiante.",
        "- Se informa a los apoderados de los estudiantes involucrados, resguardando la identidad de terceros.",
        "- El protocolo se cierra con un informe que da cuenta de las acciones, las medidas y el seguimiento.",
        "- Si la situación lo amerita, se activan en paralelo otros protocolos (accidente escolar, vulneración de derechos, etc.).",
    ])
    _cierre(doc)


def _romano(n):
    return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"][n]


def _reglamento(doc, est):
    _encabezado(doc, est, "Reglamento Interno de Convivencia Escolar")
    doc.add_paragraph("Estructura tipo y contenidos mínimos para establecimientos de enseñanza básica y media. Complete cada "
                      "apartado con la realidad del establecimiento y someta el documento a consulta del Consejo Escolar.")
    _tabla(doc, [[k, v] for k, v in _datos(est).items()], anchos=(5, 12))
    capitulos = [
        ("Introducción y fundamentos", ["Propósito del reglamento, vínculo con el Proyecto Educativo Institucional (PEI) y sellos educativos."]),
        ("Marco normativo", ["- " + n for n in NORMATIVA_BASE + [
            "Ley N° 21.128, Aula Segura.", "Ley N° 21.545, de Autismo, y Circular SIE (Res. Ex. N° 586 de 2023).",
            "Ley N° 20.609, que establece medidas contra la discriminación.", "Ley N° 20.845, de Inclusión Escolar.",
            "Decreto N° 67 de 2018, de evaluación, calificación y promoción.", "Decreto N° 24 de 2005, que reglamenta los Consejos Escolares."]]),
        ("Principios", ["- " + p for p in PRINCIPIOS] + ["- Dignidad del ser humano, no discriminación arbitraria, participación, autonomía y diversidad, legalidad, transparencia."]),
        ("Derechos y deberes de la comunidad educativa", ["Estudiantes, padres, madres y apoderados, docentes, asistentes de la educación, equipo directivo y sostenedor (art. 10 LGE)."]),
        ("Regulaciones técnico-administrativas", ["Niveles, régimen de jornada, horarios de clases, recreos y alimentación; organigrama y roles; mecanismos de comunicación con las familias; registro de asistencia y atrasos; retiro de estudiantes."]),
        ("Regulaciones sobre admisión y matrícula", ["Proceso de admisión (SAE cuando corresponda) y regulaciones sobre pagos o becas si aplican."]),
        ("Uniforme, presentación personal y dispositivos móviles", ["Uso del uniforme (Decreto N° 215 de 2009) sin que su incumplimiento impida asistir a clases; regulación del uso de dispositivos móviles."]),
        ("Seguridad, higiene y salud", ["Plan Integral de Seguridad Escolar (PISE); medidas de higiene; protocolo de accidentes escolares."]),
        ("Gestión pedagógica", ["Reglamento de evaluación y promoción, salidas pedagógicas, regulaciones sobre estudiantes embarazadas, madres y padres."]),
        ("Convivencia escolar y buen trato", ["Equipo de convivencia y sus funciones (Ley 21.809), Plan de Gestión de la Convivencia, instancias de participación (Consejo Escolar, Centro de Estudiantes, Centro de Padres)."]),
        ("Faltas, medidas y procedimientos", ["Descripción de las faltas (leves, graves y gravísimas), medidas formativas, de apoyo psicosocial, reparatorias y disciplinarias, criterios de aplicación, procedimiento con debido proceso y apelación, y mecanismos de resolución colaborativa de conflictos (mediación, negociación, arbitraje pedagógico)."]),
        ("Reconocimientos y estímulos", ["Acciones que se reconocen y forma de hacerlo."]),
        ("Protocolos de actuación", ["Se adjuntan como anexos los protocolos de actuación, cada uno con responsables, plazos, medidas de resguardo y registro."]),
        ("Aprobación, actualización y difusión", ["Revisión al menos una vez al año con consulta al Consejo Escolar; publicación en el sitio web y entrega a las familias al momento de la matrícula."]),
    ]
    for i, (titulo, lineas) in enumerate(capitulos, 1):
        doc.add_heading(f"Título {i}. {titulo}", level=1)
        _parrafos(doc, lineas)
    doc.add_heading("Anexos: protocolos de actuación", level=1)
    for d in PROTOCOLOS:
        doc.add_page_break()
        _protocolo(doc, est, d)


def _pgce(doc, est):
    from .models import AccionPME, Perfil, anio_actual

    anio = anio_actual()
    _encabezado(doc, est, f"Plan de Gestión de la Convivencia Educativa {anio}")
    doc.add_heading("I. Identificación del establecimiento educacional", level=1)
    _tabla(doc, [["Tipo de establecimiento", est.get_oferta_display()]] + [[k, v] for k, v in _datos(est).items()] +
           [["Matrícula total", ""], ["Índice de vulnerabilidad", ""]], anchos=(6, 11))
    doc.add_heading("II. Marco orientador", level=1)
    _parrafos(doc, [
        "A. Política Nacional de Convivencia Educativa (PNCE) 2024-2030: el plan se orienta a construir una convivencia democrática, inclusiva, de buen trato y bienestar, en coherencia con el eje de Convivencia y Salud Mental del Plan de Reactivación Educativa.",
        "B. Enfoque Escuela Total multinivel:",
        "- Nivel 1, promoción universal: acciones preventivas para toda la comunidad.",
        "- Nivel 2, apoyos focalizados: estrategias para grupos que requieren apoyos adicionales.",
        "- Nivel 3, intervenciones de mayor intensidad: apoyos individuales articulados con redes externas.",
    ])
    doc.add_heading("III. Articulación del PGCE con el PME (dimensión Convivencia)", level=1)
    acciones = list(AccionPME.objects.filter(plan__anio=anio, dimension="CONVIVENCIA"))
    _tabla(doc, [["Convivencia escolar", "", "", a.nombre, "", a.medios_verificacion] for a in acciones] or [["Convivencia escolar", "", "", "", "", ""]],
           encabezado=["Dimensión PME", "Objetivo estratégico", "Objetivo anual", "Acción PME", "Vinculación con el PGCE", "Medio de verificación"])
    doc.add_heading("IV. Planificación en base a datos (diagnóstico)", level=1)
    doc.add_paragraph("A. Autodiagnóstico institucional (encuestas, Consejo Escolar, registros de convivencia).")
    _tabla(doc, [["Brechas de mejora:\n1.\n2.\n3.", "Brechas de mejora:\n1.\n2.\n3.", "Brechas de mejora:\n1.\n2.\n3."]],
           encabezado=["Estudiantes", "Apoderados", "Funcionarios"])
    doc.add_paragraph("B. Análisis DIA Socioemocional. Preguntas orientadoras:")
    _parrafos(doc, ["- ¿Qué fortalezas y desafíos muestran los resultados?", "- ¿Se concentran en determinados niveles o cursos?",
                    "- ¿Qué otros datos los confirman o cuestionan?", "- ¿Qué necesidad debemos priorizar y por qué?",
                    "- ¿Requiere una estrategia universal, focalizada o ambas, según el modelo Escuela Total?",
                    "- ¿Con qué indicadores evaluaremos el avance?"])
    doc.add_paragraph("C. Vinculación con el PEI: misión, visión, sellos y valores relacionados con la convivencia.")
    doc.add_heading("V. Objetivo general y objetivos específicos", level=1)
    _tabla(doc, [["Objetivo general:"], ["Objetivo específico 1:"], ["Objetivo específico 2:"], ["Objetivo específico 3:"]])
    doc.add_heading("VI y VII. Equipo de convivencia educativa", level=1)
    equipo = [[u.usuario.get_full_name() or u.usuario.username, u.get_rol_display(), ""]
              for u in Perfil.objects.filter(establecimiento=est, rol__in=["CONVIVENCIA", "INSPECTOR"]).select_related("usuario")]
    _tabla(doc, equipo + [["", "Coordinador(a) de convivencia", ""], ["", "Dupla psicosocial", ""], ["", "Orientador(a)", ""]],
           encabezado=["Nombre", "Cargo", "Horas para el cargo"])
    _tabla(doc, [[r, ""] for r in ("Representante de estudiantes", "Representante de apoderados", "Representante de docentes",
                                   "Representante de asistentes de la educación", "Representante del sostenedor", "Director(a)")],
           encabezado=["Consejo Escolar", "Nombre"])
    doc.add_heading(f"VIII. Matriz del PGCE {anio}", level=1)
    _tabla(doc, [["", "", "", "", "", "", ""] for _ in range(5)],
           encabezado=["Objetivo específico", "Acciones", "Metas", "Plazo", "Responsables", "Recursos", "Verificadores"])
    doc.add_heading("IX. Cronograma", level=1)
    meses = ["Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    _tabla(doc, [[f"Acción {i}", ""] + [""] * len(meses) for i in range(1, 7)], encabezado=["Acción", "Responsable"] + meses)
    _cierre(doc, ("Encargado(a) de Convivencia", "Director(a)", "Consejo Escolar"))


def _formato(doc, est, d, estudiante=None, responsable=""):
    _encabezado(doc, est, d["titulo"])
    base = [["Estudiante", ""], ["RUT", ""], ["Curso", ""], ["Apoderado(a)", ""], ["Fecha", ""], ["Responsable", responsable]]
    if estudiante is not None:
        from datetime import date
        base[0][1] = str(estudiante)
        base[1][1] = estudiante.rut_formateado
        base[2][1] = estudiante.curso.nombre_corto if estudiante.curso else ""
        base[3][1] = " · ".join(x for x in (estudiante.apoderado_nombre, estudiante.apoderado_telefono) if x)
        base[4][1] = f"{date.today():%d-%m-%Y}"
    clave = d["clave"]
    if clave == "acta-activacion":
        _tabla(doc, base + [["Protocolo activado", ""], ["Quién informa y cómo se tomó conocimiento", ""]], anchos=(5, 12))
        for t in ("Descripción de los hechos (textual cuando corresponde)", "Medidas de resguardo inmediatas",
                  "Aviso a la familia (fecha, hora, medio)", "Denuncia o derivación (institución, fecha, folio)", "Próximas acciones y plazos"):
            doc.add_heading(t, level=2)
            doc.add_paragraph("\n\n")
    elif clave == "paec":
        _tabla(doc, base + [["Diagnóstico (si existe) y tratantes", ""], ["Adulto encargado(a) / acompañantes", ""]], anchos=(5, 12))
        for t in ("Fortalezas e intereses del estudiante", "Gatillantes o estresores conocidos", "Señales de alerta (fase inicial)",
                  "Estrategias que le ayudan a regularse", "Espacio de calma y apoyos sensoriales", "Acuerdos con la familia y forma de contacto"):
            doc.add_heading(t, level=2)
            doc.add_paragraph("\n")
        doc.add_heading("Bitácora de registro", level=2)
        _tabla(doc, [["", "", "", "", "", ""] for _ in range(8)],
               encabezado=["Fecha y hora", "Contexto", "Gatillante", "Duración", "Acciones realizadas", "Resultado"])
    elif clave == "derivacion":
        _tabla(doc, base + [["Institución a la que se deriva", ""], ["Motivo de la derivación", ""], ["Acciones previas del establecimiento", ""],
                            ["Contacto en el establecimiento", ""], ["Consentimiento del apoderado(a)", "Sí / No / No aplica"]], anchos=(5, 12))
    elif clave == "carta-compromiso":
        _tabla(doc, base, anchos=(5, 12))
        doc.add_paragraph("Motivo:")
        _tabla(doc, [["", "", "", ""] for _ in range(5)], encabezado=["Compromiso", "Responsable", "Plazo", "Seguimiento"])
        _cierre(doc, ("Estudiante", "Apoderado(a)", "Encargado(a) de Convivencia"))
        return
    elif clave == "informe-cierre":
        _tabla(doc, base + [["Protocolo", ""], ["Fecha de activación", ""], ["Fecha de cierre", ""]], anchos=(5, 12))
        for t in ("Síntesis de los hechos", "Acciones realizadas", "Medidas aplicadas", "Resultados y estado actual", "Seguimiento acordado"):
            doc.add_heading(t, level=2)
            doc.add_paragraph("\n")
    _cierre(doc)


def generar_docx(clave, est, estudiante=None, responsable=""):
    from docx import Document
    from docx.shared import Pt

    d = TODOS[clave]
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name, estilo.font.size = "Calibri", Pt(11)
    if clave == "reglamento-interno":
        _reglamento(doc, est)
    elif clave == "pgce":
        _pgce(doc, est)
    elif d in FORMATOS:
        _formato(doc, est, d, estudiante, responsable)
    else:
        _protocolo(doc, est, d)
    salida = BytesIO()
    doc.save(salida)
    return salida.getvalue()
