from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .rut import formatear_rut, normalizar_rut, validar_rut

NOTA_MINIMA = Decimal("1.0")
NOTA_MAXIMA = Decimal("7.0")
NOTA_APROBACION = Decimal("4.0")


def anio_actual():
    return timezone.localdate().year


class Establecimiento(models.Model):
    """Datos del establecimiento que aparecen en los informes (se usa el primero)."""

    nombre = models.CharField(max_length=200)
    rbd = models.CharField("RBD", max_length=20, blank=True)
    direccion = models.CharField("dirección", max_length=200, blank=True)
    comuna = models.CharField(max_length=100, blank=True)
    telefono = models.CharField("teléfono", max_length=50, blank=True)
    director = models.CharField("nombre del director(a)", max_length=200, blank=True)
    jefe_utp = models.CharField("nombre del jefe(a) de UTP", max_length=200, blank=True)
    region = models.CharField("región", max_length=100, blank=True)
    resolucion_reconocimiento = models.CharField(
        "decreto o resolución de reconocimiento oficial", max_length=200, blank=True,
        help_text="Ej.: Resolución Exenta N° 1234 de 1981. Aparece en el certificado anual de estudios.")
    alta_concentracion = models.BooleanField(
        "establecimiento con 80 % o más de alumnos prioritarios", default=False,
        help_text="Si se marca, los docentes de pre-kínder a 4° básico tienen proporción 60/40 (Ley 20.903).")

    class Meta:
        verbose_name = "establecimiento"
        verbose_name_plural = "establecimiento"

    def __str__(self):
        return self.nombre

    @classmethod
    def actual(cls):
        return cls.objects.first() or cls(nombre="Establecimiento educacional")


class Perfil(models.Model):
    class Rol(models.TextChoices):
        SOSTENEDOR = "SOSTENEDOR", "Sostenedor(a)"
        DIRECTOR = "DIRECTOR", "Director(a)"
        UTP = "UTP", "Jefe(a) de UTP"
        INSPECTOR = "INSPECTOR", "Inspector(a) general"
        CONVIVENCIA = "CONVIVENCIA", "Encargado(a) de convivencia"
        PROFESOR = "PROFESOR", "Profesor(a)"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.PROFESOR)
    rut = models.CharField("RUT", max_length=15, blank=True, validators=[validar_rut])

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} ({self.get_rol_display()})"

    @property
    def es_gestion(self):
        """Dirección y UTP: editan todo y configuran la plataforma."""
        return self.rol in (self.Rol.DIRECTOR, self.Rol.UTP)

    @property
    def ve_todo(self):
        """Roles que consultan todos los cursos y niveles."""
        return self.rol != self.Rol.PROFESOR

    @property
    def gestiona_convivencia(self):
        return self.rol in (self.Rol.DIRECTOR, self.Rol.UTP, self.Rol.INSPECTOR, self.Rol.CONVIVENCIA)

    def save(self, *args, **kwargs):
        if self.rut:
            self.rut = normalizar_rut(self.rut)
        super().save(*args, **kwargs)
        # Director(a) y Jefe(a) de UTP pueden entrar al panel de administración.
        debe_ser_staff = self.es_gestion or self.usuario.is_superuser
        if self.usuario.is_staff != debe_ser_staff:
            self.usuario.is_staff = debe_ser_staff
            self.usuario.save(update_fields=["is_staff"])


class Nivel(models.Model):
    class Ensenanza(models.TextChoices):
        PARVULARIA = "PARVULARIA", "Educación Parvularia"
        BASICA = "BASICA", "Enseñanza Básica"
        MEDIA = "MEDIA", "Enseñanza Media"

    nombre = models.CharField(max_length=50, unique=True, help_text="Ej.: 1° Básico, III Medio")
    orden = models.PositiveSmallIntegerField(default=0, help_text="Para ordenar los niveles de menor a mayor")
    ensenanza = models.CharField("tipo de enseñanza", max_length=20, choices=Ensenanza.choices, blank=True)
    decreto_plan_estudios = models.CharField(
        "decreto del plan de estudios", max_length=200, blank=True,
        help_text="Aparece en el certificado anual de estudios. Ej.: Decreto Exento N° 2960 de 2012.")

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name_plural = "niveles"

    def __str__(self):
        return self.nombre


class Curso(models.Model):
    nivel = models.ForeignKey(Nivel, on_delete=models.PROTECT, related_name="cursos")
    letra = models.CharField(max_length=5, help_text="Ej.: A, B")
    anio = models.PositiveSmallIntegerField("año", default=anio_actual)
    profesor_jefe = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="jefaturas", verbose_name="profesor(a) jefe",
    )

    class Meta:
        ordering = ["-anio", "nivel__orden", "letra"]
        constraints = [models.UniqueConstraint(fields=["nivel", "letra", "anio"], name="curso_unico")]

    def __str__(self):
        return f"{self.nivel} {self.letra} ({self.anio})"

    @property
    def nombre_corto(self):
        return f"{self.nivel} {self.letra}"


class Asignatura(models.Model):
    class Tipo(models.TextChoices):
        ASIGNATURA = "ASIGNATURA", "Asignatura del plan de estudios"
        TALLER = "TALLER", "Taller JEC"

    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField("código", max_length=20, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ASIGNATURA)
    incide_en_promedio = models.BooleanField(
        "incide en el promedio y la promoción", default=True,
        help_text="Desmarcar para Religión, Orientación o talleres evaluados con concepto (Decreto 67/2018).")

    class Meta:
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class AsignaturaCurso(models.Model):
    """Carga académica: qué asignatura se dicta en qué curso y quién la dicta."""

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="asignaturas_curso")
    asignatura = models.ForeignKey(Asignatura, on_delete=models.PROTECT, related_name="cursos")
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="asignaturas_curso", verbose_name="profesor(a)",
    )
    horas_semanales = models.DecimalField("horas semanales", max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = "asignatura del curso (carga académica)"
        verbose_name_plural = "carga académica"
        ordering = ["curso", "asignatura__tipo", "asignatura__orden", "asignatura__nombre"]
        constraints = [models.UniqueConstraint(fields=["curso", "asignatura"], name="asignatura_curso_unica")]

    def __str__(self):
        return f"{self.asignatura} – {self.curso.nombre_corto}"


class Estudiante(models.Model):
    rut = models.CharField("RUT", max_length=15, unique=True, validators=[validar_rut])
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name="estudiantes")
    # Contacto
    direccion = models.CharField("dirección", max_length=200, blank=True)
    comuna = models.CharField(max_length=100, blank=True)
    codigo_comuna = models.CharField("código comuna (SIGE)", max_length=10, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    celular = models.CharField(max_length=30, blank=True)
    email = models.EmailField("correo electrónico", blank=True)
    # Datos de la nómina SIGE
    codigo_etnia = models.CharField("código etnia (SIGE)", max_length=5, blank=True,
                                    help_text="0 = no pertenece a pueblo originario.")
    fecha_incorporacion = models.DateField("fecha de incorporación al curso", null=True, blank=True)
    fecha_retiro = models.DateField("fecha de retiro", null=True, blank=True)
    promedio_sige = models.DecimalField("promedio final informado en SIGE", max_digits=2, decimal_places=1,
                                        null=True, blank=True)
    # Apoderado y emergencias
    apoderado_nombre = models.CharField("nombre del apoderado(a)", max_length=200, blank=True)
    apoderado_rut = models.CharField("RUT del apoderado(a)", max_length=15, blank=True, validators=[validar_rut])
    apoderado_telefono = models.CharField("teléfono del apoderado(a)", max_length=30, blank=True)
    telefono_emergencia = models.CharField("teléfono de emergencia", max_length=30, blank=True)
    contacto_emergencia = models.CharField("contacto de emergencia", max_length=200, blank=True)
    genero = models.CharField("género", max_length=1, choices=[("F", "Femenino"), ("M", "Masculino")], blank=True)
    porcentaje_asistencia = models.DecimalField(
        "% de asistencia", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Asistencia anual; se puede cargar desde la nómina SIGE.")
    activo = models.BooleanField(default=True, help_text="Desmarcar si el estudiante se retiró")

    class Meta:
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]

    def __str__(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        self.rut = normalizar_rut(self.rut)
        if self.apoderado_rut:
            self.apoderado_rut = normalizar_rut(self.apoderado_rut)
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return " ".join(p for p in [self.apellido_paterno, self.apellido_materno] if p) + f", {self.nombres}"

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut)


class Evaluacion(models.Model):
    class Semestre(models.IntegerChoices):
        PRIMERO = 1, "1er semestre"
        SEGUNDO = 2, "2do semestre"

    asignatura_curso = models.ForeignKey(AsignaturaCurso, on_delete=models.CASCADE, related_name="evaluaciones")
    nombre = models.CharField(max_length=100)
    fecha = models.DateField(null=True, blank=True)
    semestre = models.PositiveSmallIntegerField(choices=Semestre.choices, default=Semestre.PRIMERO)
    ponderacion = models.DecimalField(
        "ponderación", max_digits=5, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Peso relativo dentro del semestre. Use 1 para que todas pesen igual, o porcentajes (ej. 30, 70).",
    )

    class Meta:
        verbose_name = "evaluación"
        verbose_name_plural = "evaluaciones"
        ordering = ["semestre", "fecha", "id"]

    def __str__(self):
        return f"{self.nombre} (S{self.semestre})"


class Calificacion(models.Model):
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name="calificaciones")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="calificaciones")
    nota = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(NOTA_MINIMA), MaxValueValidator(NOTA_MAXIMA)],
    )

    class Meta:
        verbose_name = "calificación"
        verbose_name_plural = "calificaciones"
        constraints = [models.UniqueConstraint(fields=["evaluacion", "estudiante"], name="calificacion_unica")]

    def __str__(self):
        return f"{self.estudiante} – {self.evaluacion}: {self.nota}"


class Anotacion(models.Model):
    class Tipo(models.TextChoices):
        POSITIVA = "POSITIVA", "Positiva"
        NEGATIVA = "NEGATIVA", "Negativa"
        OBSERVACION = "OBSERVACION", "Observación"

    class Gravedad(models.TextChoices):
        LEVE = "LEVE", "Leve"
        GRAVE = "GRAVE", "Grave"
        GRAVISIMA = "GRAVISIMA", "Gravísima"

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="anotaciones")
    fecha = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OBSERVACION)
    gravedad = models.CharField(
        max_length=20, choices=Gravedad.choices, blank=True,
        help_text="Solo para anotaciones negativas (según Reglamento de Convivencia).",
    )
    asignatura = models.ForeignKey(Asignatura, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.TextField("descripción")
    medida = models.TextField("medida o acción tomada", blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "anotación"
        verbose_name_plural = "anotaciones"
        ordering = ["-fecha", "-creada"]

    def __str__(self):
        return f"{self.get_tipo_display()} – {self.estudiante} ({self.fecha:%d-%m-%Y})"


class SolicitudCambio(models.Model):
    """Cambio de datos de un estudiante pedido por su profesor(a) jefe.

    No se aplica hasta que Dirección o UTP lo aprueba.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="solicitudes")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name="solicitudes_cambio")
    cambios = models.JSONField(help_text="{campo: {'antes': valor, 'despues': valor}}")
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    revisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="solicitudes_revisadas")
    revisada = models.DateTimeField(null=True, blank=True)
    comentario_revision = models.TextField("comentario de la revisión", blank=True)

    class Meta:
        verbose_name = "solicitud de modificación"
        verbose_name_plural = "solicitudes de modificación"
        ordering = ["-creada"]

    def __str__(self):
        return f"Solicitud {self.get_estado_display().lower()} – {self.estudiante}"

    def cambios_legibles(self):
        """[(etiqueta, antes, después)] para mostrar en pantalla."""
        filas = []
        for campo, valores in self.cambios.items():
            try:
                etiqueta = Estudiante._meta.get_field(campo).verbose_name
            except Exception:
                etiqueta = campo
            antes, despues = valores.get("antes"), valores.get("despues")
            if campo == "fecha_nacimiento":
                antes, despues = (_fecha_legible(antes), _fecha_legible(despues))
            elif campo in ("rut", "apoderado_rut"):
                antes, despues = formatear_rut(antes) if antes else "", formatear_rut(despues) if despues else ""
            filas.append((str(etiqueta).capitalize(), antes or "—", despues or "—"))
        return filas

    def aplicar(self):
        """Copia los cambios al estudiante y lo guarda. Lanza ValidationError si ya no son válidos."""
        import datetime as dt

        est = self.estudiante
        for campo, valores in self.cambios.items():
            valor = valores.get("despues") or ""
            if campo == "fecha_nacimiento":
                valor = dt.date.fromisoformat(valor) if valor else None
            setattr(est, campo, valor)
        if est.rut:
            est.rut = normalizar_rut(est.rut)
        est.full_clean()
        est.save()


def _fecha_legible(iso):
    if not iso:
        return ""
    a, m, d = iso.split("-")
    return f"{d}-{m}-{a}"


class Comentario(models.Model):
    """Retroalimentación que los usuarios envían desde cualquier pantalla."""

    class Tipo(models.TextChoices):
        PROBLEMA = "PROBLEMA", "Algo no funciona"
        SUGERENCIA = "SUGERENCIA", "Sugerencia o idea"
        OTRO = "OTRO", "Otro comentario"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.SUGERENCIA)
    pagina = models.CharField("página", max_length=300, blank=True)
    texto = models.TextField("comentario")
    creado = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "comentario de usuarios"
        verbose_name_plural = "comentarios de usuarios"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.get_tipo_display()} – {self.usuario} ({self.creado:%d-%m-%Y})"


class Funcionario(models.Model):
    """Ficha de docentes y demás funcionarios del establecimiento."""

    class Cargo(models.TextChoices):
        DOCENTE = "DOCENTE", "Docente de aula"
        DIRECTIVO = "DIRECTIVO", "Docente directivo"
        TECNICO = "TECNICO", "Docente técnico-pedagógico"
        ASISTENTE = "ASISTENTE", "Asistente de la educación"

    class Contrato(models.TextChoices):
        TITULAR = "TITULAR", "Titular"
        CONTRATA = "CONTRATA", "Contrata"
        OTRO = "OTRO", "Otro (reemplazo, honorarios, Código del Trabajo)"

    class Proporcion(models.TextChoices):
        AUTOMATICA = "AUTO", "Automática según la Ley 20.903"
        P65 = "65", "65/35"
        P60 = "60", "60/40"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="funcionario", verbose_name="usuario de la plataforma",
                                   help_text="Opcional: vincula la ficha con su cuenta de acceso.")
    rut = models.CharField("RUT", max_length=15, unique=True, validators=[validar_rut])
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True)
    cargo = models.CharField(max_length=20, choices=Cargo.choices, default=Cargo.DOCENTE)
    titulo = models.CharField("título profesional", max_length=200, blank=True)
    mencion = models.CharField("mención o especialidad", max_length=200, blank=True)
    tipo_contrato = models.CharField("tipo de contrato", max_length=20, choices=Contrato.choices,
                                     default=Contrato.TITULAR)
    horas_contrato = models.DecimalField("horas de contrato (semanales)", max_digits=4, decimal_places=1,
                                         validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("44"))])
    primer_ciclo = models.BooleanField(
        "hace clases entre pre-kínder y 4° básico", default=False,
        help_text="Con alta concentración de alumnos prioritarios, estos docentes tienen proporción 60/40.")
    proporcion = models.CharField("proporción lectiva/no lectiva", max_length=4, choices=Proporcion.choices,
                                  default=Proporcion.AUTOMATICA)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("correo electrónico", blank=True)
    fecha_ingreso = models.DateField("fecha de ingreso", null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]
        verbose_name = "funcionario(a)"
        verbose_name_plural = "funcionarios"

    def __str__(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        self.rut = normalizar_rut(self.rut)
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return " ".join(p for p in [self.nombres, self.apellido_paterno, self.apellido_materno] if p)

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut)

    def porcentaje_lectivo(self, establecimiento=None):
        """65 o 60 (Ley 20.903). None si no corresponde (no es docente de aula)."""
        if self.proporcion == self.Proporcion.P65:
            return 65
        if self.proporcion == self.Proporcion.P60:
            return 60
        if self.cargo != self.Cargo.DOCENTE:
            return None
        establecimiento = establecimiento or Establecimiento.actual()
        if establecimiento.alta_concentracion and self.primer_ciclo:
            return 60
        return 65

    def distribucion(self, establecimiento=None):
        """(porcentaje, horas lectivas, horas no lectivas) en horas cronológicas."""
        pct = self.porcentaje_lectivo(establecimiento)
        if pct is None:
            return None, None, None
        lectivas = (self.horas_contrato * pct / 100).quantize(Decimal("0.01"))
        return pct, lectivas, self.horas_contrato - lectivas
