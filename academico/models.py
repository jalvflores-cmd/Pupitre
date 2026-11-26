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
        DIRECTOR = "DIRECTOR", "Director(a)"
        UTP = "UTP", "Jefe(a) de UTP"
        PROFESOR = "PROFESOR", "Profesor(a)"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.PROFESOR)
    rut = models.CharField("RUT", max_length=12, blank=True, validators=[validar_rut])

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} ({self.get_rol_display()})"

    @property
    def es_gestion(self):
        return self.rol in (self.Rol.DIRECTOR, self.Rol.UTP)

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
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej.: 1° Básico, III Medio")
    orden = models.PositiveSmallIntegerField(default=0, help_text="Para ordenar los niveles de menor a mayor")

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
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField("código", max_length=20, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

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

    class Meta:
        verbose_name = "asignatura del curso (carga académica)"
        verbose_name_plural = "carga académica"
        ordering = ["curso", "asignatura__orden", "asignatura__nombre"]
        constraints = [models.UniqueConstraint(fields=["curso", "asignatura"], name="asignatura_curso_unica")]

    def __str__(self):
        return f"{self.asignatura} – {self.curso.nombre_corto}"


class Estudiante(models.Model):
    rut = models.CharField("RUT", max_length=12, unique=True, validators=[validar_rut])
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name="estudiantes")
    # Contacto
    direccion = models.CharField("dirección", max_length=200, blank=True)
    comuna = models.CharField(max_length=100, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("correo electrónico", blank=True)
    # Apoderado y emergencias
    apoderado_nombre = models.CharField("nombre del apoderado(a)", max_length=200, blank=True)
    apoderado_rut = models.CharField("RUT del apoderado(a)", max_length=12, blank=True, validators=[validar_rut])
    apoderado_telefono = models.CharField("teléfono del apoderado(a)", max_length=30, blank=True)
    telefono_emergencia = models.CharField("teléfono de emergencia", max_length=30, blank=True)
    contacto_emergencia = models.CharField("contacto de emergencia", max_length=200, blank=True)
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
