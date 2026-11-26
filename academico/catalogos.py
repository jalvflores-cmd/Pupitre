"""Listas iniciales de cada establecimiento (luego son editables en Configuración)."""

PROTOCOLOS = [
    ("VULNERACION", "Vulneración de derechos"),
    ("ABUSO_SEXUAL", "Agresiones sexuales y hechos de connotación sexual"),
    ("MALTRATO_ESTUDIANTES", "Maltrato, acoso escolar o violencia entre estudiantes"),
    ("MALTRATO_ADULTO", "Maltrato de adulto a estudiante"),
    ("MALTRATO_A_FUNCIONARIO", "Maltrato a funcionario(a) de la comunidad"),
    ("DROGAS_ALCOHOL", "Consumo o porte de drogas y alcohol"),
    ("ACCIDENTE", "Accidente escolar"),
    ("AUTOLESION", "Conducta autolesiva o riesgo suicida"),
    ("DESREGULACION", "Desregulación emocional y conductual"),
    ("EMBARAZO", "Retención de estudiantes embarazadas, madres y padres"),
    ("AULA_SEGURA", "Ley Aula Segura (expulsión o cancelación de matrícula)"),
    ("OTRO", "Otro protocolo del Reglamento Interno"),
]
REDES = [
    ("MEJOR_NINEZ", "Servicio Mejor Niñez"),
    ("SENAME", "SENAME (antecedente histórico)"),
    ("OLN", "Oficina Local de la Niñez (OLN)"),
    ("OPD", "Oficina de Protección de Derechos (OPD)"),
    ("TRIBUNAL", "Tribunal de Familia (medida de protección)"),
    ("CESFAM", "CESFAM / Salud primaria"),
    ("COSAM", "COSAM / Salud mental"),
    ("SENDA", "SENDA Previene"),
    ("FISCALIA", "Fiscalía / Programa de víctimas"),
    ("HPV", "Habilidades para la Vida (JUNAEB)"),
    ("OTRA", "Otra institución"),
]



def sembrar_catalogos(establecimiento):
    from .models import OpcionCatalogo

    for tipo, lista in (("PROTOCOLO", PROTOCOLOS), ("RED", REDES)):
        for i, (codigo, nombre) in enumerate(lista):
            OpcionCatalogo.todos.get_or_create(establecimiento=establecimiento, tipo=tipo, codigo=codigo,
                                               defaults={"nombre": nombre, "orden": i})
