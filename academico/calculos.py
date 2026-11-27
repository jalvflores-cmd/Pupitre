"""Cálculo de promedios y situación final (escala chilena 1,0 a 7,0).

Reglas:
- Promedio semestral de una asignatura: promedio ponderado de sus evaluaciones del semestre.
- Promedio final de la asignatura: promedio de los semestres con notas.
- Promedio general: promedio de los promedios finales de cada asignatura.
- Todos los promedios se redondean a un decimal (0,05 sube).
- Promoción (Decreto 67/2018, sin considerar asistencia):
    * todas las asignaturas aprobadas, o
    * 1 asignatura reprobada y promedio general >= 4,5, o
    * 2 asignaturas reprobadas y promedio general >= 5,0.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .models import NOTA_APROBACION, AsignaturaCurso, Calificacion

UN_DECIMAL = Decimal("0.1")


def redondear(valor):
    if valor is None:
        return None
    return Decimal(valor).quantize(UN_DECIMAL, rounding=ROUND_HALF_UP)


def promedio_ponderado(pares):
    """pares: iterable de (nota, ponderación)."""
    pares = [(Decimal(n), Decimal(p)) for n, p in pares if n is not None]
    total_pesos = sum(p for _, p in pares)
    if not pares or total_pesos == 0:
        return None
    return redondear(sum(n * p for n, p in pares) / total_pesos)


def promedio_simple(valores):
    valores = [Decimal(v) for v in valores if v is not None]
    if not valores:
        return None
    return redondear(sum(valores) / len(valores))


@dataclass
class PromedioAsignatura:
    asignatura_curso: AsignaturaCurso
    notas: dict = field(default_factory=dict)  # evaluacion_id -> nota
    s1: Decimal | None = None
    s2: Decimal | None = None
    final: Decimal | None = None
    aplica: bool = True  # False: Religión de otro credo

    @property
    def incide(self):
        return self.aplica and self.asignatura_curso.asignatura.incide_en_promedio

    @property
    def con_concepto(self):
        return self.asignatura_curso.asignatura.con_concepto

    @property
    def aprobada(self):
        return self.final is None or self.final >= NOTA_APROBACION

    @property
    def concepto(self):
        return concepto(self.final)


def calcular_promedios(evaluaciones, notas_por_evaluacion):
    """Devuelve (s1, s2, final) para un estudiante en una asignatura."""
    por_semestre = defaultdict(list)
    for ev in evaluaciones:
        nota = notas_por_evaluacion.get(ev.id)
        if nota is not None:
            por_semestre[ev.semestre].append((nota, ev.ponderacion))
    s1 = promedio_ponderado(por_semestre[1])
    s2 = promedio_ponderado(por_semestre[2])
    return s1, s2, promedio_simple([s1, s2])


@dataclass
class ResumenEstudiante:
    estudiante: object
    asignaturas: list  # list[PromedioAsignatura], en el mismo orden que las asignaturas del curso
    promedio_s1: Decimal | None = None
    promedio_s2: Decimal | None = None
    promedio_general: Decimal | None = None
    reprobadas: list = field(default_factory=list)
    situacion: str = ""


ASISTENCIA_MINIMA = Decimal("85")


def situacion_final(promedio_general, reprobadas, asistencia=None, activo=True):
    if not activo:
        return "Retirado(a)"
    if promedio_general is None:
        return "Sin calificaciones"
    if asistencia is not None and asistencia < ASISTENCIA_MINIMA:
        n = len(reprobadas)
        academico = n == 0 or (n == 1 and promedio_general >= Decimal("4.5")) or (n == 2 and promedio_general >= Decimal("5.0"))
        if academico:
            return "Revisar asistencia (< 85 %)"
    n = len(reprobadas)
    if n == 0:
        return "Promovido(a)"
    if n == 1 and promedio_general >= Decimal("4.5"):
        return "Promovido(a)"
    if n == 2 and promedio_general >= Decimal("5.0"):
        return "Promovido(a)"
    return "Reprobado(a)"


def resumen_curso(curso, asignaturas_curso=None, estudiantes=None):
    """Calcula los promedios de todos los estudiantes del curso con pocas consultas.

    asignaturas_curso: limita a estas asignaturas (por defecto, todas las del curso).
    """
    if asignaturas_curso is None:
        asignaturas_curso = list(curso.asignaturas_curso.select_related("asignatura", "profesor"))
    if estudiantes is None:
        estudiantes = list(curso.estudiantes.filter(activo=True))
    evaluaciones = defaultdict(list)
    for ac in asignaturas_curso:
        evaluaciones[ac.id] = list(ac.evaluaciones.all())

    notas = defaultdict(dict)  # (estudiante_id, ac_id) -> {evaluacion_id: nota}
    for c in Calificacion.objects.filter(
        evaluacion__asignatura_curso__in=asignaturas_curso, estudiante__in=estudiantes
    ).values("estudiante_id", "evaluacion_id", "evaluacion__asignatura_curso_id", "nota"):
        notas[(c["estudiante_id"], c["evaluacion__asignatura_curso_id"])][c["evaluacion_id"]] = c["nota"]

    resumenes = []
    for est in estudiantes:
        filas = []
        for ac in asignaturas_curso:
            if not est.cursa(ac.asignatura):
                filas.append(PromedioAsignatura(ac, {}, aplica=False))
                continue
            notas_ac = notas[(est.id, ac.id)]
            s1, s2, final = calcular_promedios(evaluaciones[ac.id], notas_ac)
            filas.append(PromedioAsignatura(ac, notas_ac, s1, s2, final))
        inciden = [f for f in filas if f.incide]
        prom_general = promedio_simple([f.final for f in inciden])
        reprobadas = [f for f in inciden if not f.aprobada]
        resumenes.append(
            ResumenEstudiante(
                estudiante=est,
                asignaturas=filas,
                promedio_s1=promedio_simple([f.s1 for f in inciden]),
                promedio_s2=promedio_simple([f.s2 for f in inciden]),
                promedio_general=prom_general,
                reprobadas=reprobadas,
                situacion=situacion_final(prom_general, reprobadas, est.porcentaje_asistencia, est.activo),
            )
        )
    return asignaturas_curso, evaluaciones, resumenes


def formato_nota(valor):
    """Muestra la nota con coma decimal, como se usa en Chile."""
    if valor is None or valor == "":
        return ""
    return f"{Decimal(valor):.1f}".replace(".", ",")


_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]


def nota_en_palabras(valor):
    """Decimal('6.5') -> 'seis coma cinco' (como se escribe en los certificados)."""
    if valor is None:
        return ""
    entero, decimal = f"{Decimal(valor):.1f}".split(".")
    return f"{_UNIDADES[int(entero)]} coma {_UNIDADES[int(decimal)]}"


CONCEPTOS = [(Decimal("6.0"), "MB", "Muy bueno"), (Decimal("5.0"), "B", "Bueno"),
             (Decimal("4.0"), "S", "Suficiente"), (Decimal("1.0"), "I", "Insuficiente")]


# Equivalencia de cada concepto al ingresarlo (cae dentro del tramo de CONCEPTOS, así el concepto se conserva)
EQUIVALENCIAS = {"MB": Decimal("6.5"), "B": Decimal("5.5"), "S": Decimal("4.5"), "I": Decimal("3.0")}


def usa_conceptos(curso):
    """El establecimiento evalúa con conceptos de 1° a 4° básico y el curso es de esos niveles."""
    from .curriculo import grado_de_curso

    est = getattr(curso, "establecimiento", None)
    if not curso or not getattr(est, "conceptos_basica", False):
        return False
    grado = grado_de_curso(curso)
    return grado is not None and 1 <= grado <= 4


def concepto(valor, largo=False):
    """Concepto para asignaturas que no inciden en el promedio (Religión, Orientación, talleres)."""
    if valor is None:
        return ""
    for minimo, sigla, nombre in CONCEPTOS:
        if Decimal(valor) >= minimo:
            return nombre if largo else sigla
    return "Insuficiente" if largo else "I"
