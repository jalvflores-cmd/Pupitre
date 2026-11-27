from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .rut import formatear_rut, normalizar_rut, validar_rut
from .tenencia import DeEstablecimiento, PorEstablecimientoManager, establecimiento_actual

NOTA_MINIMA = Decimal("1.0")
NOTA_MAXIMA = Decimal("7.0")
NOTA_APROBACION = Decimal("4.0")


def anio_actual():
    return timezone.localdate().year


MODULOS = [
    ("curricular", "Gestión curricular (cursos, notas, informes)", True),
    ("convivencia", "Convivencia escolar", True),
    ("funcionarios", "Funcionarios", True),
    ("asistencia_personal", "Asistencia del personal", False),
    ("inventario", "Inventario y recursos", False),
    ("sep", "Rendición SEP / PME", False),
]
MODULOS_DISPONIBLES = [m for m in MODULOS if m[2]]


def modulos_por_defecto():
    return [m[0] for m in MODULOS_DISPONIBLES]


class Establecimiento(models.Model):
    """Un establecimiento de la plataforma, con sus datos, usuarios, cursos y estudiantes."""

    class Oferta(models.TextChoices):
        BASICA = "BASICA", "Escuela básica"
        HC = "HC", "Liceo Científico-Humanista"
        TP = "TP", "Liceo Técnico-Profesional"
        POLIVALENTE = "POLIVALENTE", "Liceo Polivalente (HC y TP)"
        COMPLETO = "COMPLETO", "Básica y Media"

    nombre = models.CharField(max_length=200)
    oferta = models.CharField("tipo de establecimiento", max_length=20, choices=Oferta.choices, default=Oferta.BASICA)
    activo = models.BooleanField(default=True)
    modulos = models.JSONField("módulos activos", default=modulos_por_defecto, blank=True)
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
    logo = models.BinaryField("logo institucional", null=True, blank=True, editable=False)
    color_principal = models.CharField(
        "color institucional", max_length=7, blank=True,
        help_text="Color del menú y los botones. Vacío = azul de Pupitre.")
    pie_documentos = models.CharField(
        "texto al pie de los documentos internos", max_length=200, blank=True,
        help_text="Ej.: lema o dirección del establecimiento. Aparece en Excel y entrevistas (no en documentos oficiales).")
    respaldo_carpeta_extra = models.CharField(
        "carpeta adicional para respaldos", max_length=300, blank=True,
        help_text="Opcional. Ej.: E:\\Respaldos Pupitre (disco externo). Cada respaldo también se copia ahí.")
    respaldo_conservar = models.PositiveSmallIntegerField(
        "respaldos a conservar", default=30, help_text="Los más antiguos se borran automáticamente.")

    class Meta:
        verbose_name = "establecimiento"
        verbose_name_plural = "establecimientos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def actual(cls):
        """El establecimiento con que se está trabajando (o el primero, en la instalación de un solo colegio)."""
        est = establecimiento_actual()
        if est is not None:
            return est
        return cls.objects.order_by("pk").first() or cls(nombre="Establecimiento educacional")

    def tiene_modulo(self, codigo):
        return codigo in (self.modulos or [])


class Perfil(models.Model):
    class Rol(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Superadministrador(a) de la plataforma"
        SOSTENEDOR = "SOSTENEDOR", "Sostenedor(a)"
        DIRECTOR = "DIRECTOR", "Director(a)"
        UTP = "UTP", "Jefe(a) de UTP"
        INSPECTOR = "INSPECTOR", "Inspector(a) general"
        CONVIVENCIA = "CONVIVENCIA", "Encargado(a) de convivencia"
        PROFESOR = "PROFESOR", "Profesor(a)"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.PROFESOR)
    rut = models.CharField("RUT", max_length=15, blank=True, validators=[validar_rut])
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, null=True, blank=True,
                                        related_name="perfiles",
                                        help_text="Vacío solo para el superadministrador de la plataforma.")

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} ({self.get_rol_display()})"

    @property
    def es_gestion(self):
        """Dirección y UTP: editan todo y configuran la plataforma."""
        return self.rol in (self.Rol.DIRECTOR, self.Rol.UTP, self.Rol.SUPERADMIN)

    @property
    def es_superadmin(self):
        return self.rol == self.Rol.SUPERADMIN

    @property
    def ve_todo(self):
        """Roles que consultan todos los cursos y niveles."""
        return self.rol != self.Rol.PROFESOR

    @property
    def gestiona_convivencia(self):
        return self.rol in (self.Rol.DIRECTOR, self.Rol.UTP, self.Rol.INSPECTOR, self.Rol.CONVIVENCIA,
                            self.Rol.SUPERADMIN)

    def save(self, *args, **kwargs):
        if self.rut:
            self.rut = normalizar_rut(self.rut)
        if not self.establecimiento_id and self.rol != self.Rol.SUPERADMIN:
            from .tenencia import establecimiento_por_defecto
            self.establecimiento = establecimiento_por_defecto()
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


class Curso(DeEstablecimiento):
    class Modalidad(models.TextChoices):
        HC = "HC", "Científico-Humanista"
        TP = "TP", "Técnico-Profesional"

    nivel = models.ForeignKey(Nivel, on_delete=models.PROTECT, related_name="cursos")
    letra = models.CharField(max_length=5, help_text="Ej.: A, B")
    anio = models.PositiveSmallIntegerField("año", default=anio_actual)
    profesor_jefe = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="jefaturas", verbose_name="profesor(a) jefe",
    )
    modalidad = models.CharField(max_length=2, choices=Modalidad.choices, blank=True,
                                 help_text="Solo Enseñanza Media.")
    especialidad = models.CharField(max_length=120, blank=True, help_text="Solo TP. Ej.: Administración")
    mencion = models.CharField("mención", max_length=120, blank=True, help_text="Solo TP. Ej.: Recursos Humanos")
    decreto_plan_estudios = models.CharField(
        "decreto del plan de estudios", max_length=200, blank=True,
        help_text="Si se deja vacío se usa el del nivel. Útil en Media TP (cada especialidad tiene el suyo).")

    class Meta:
        ordering = ["-anio", "nivel__orden", "letra"]
        constraints = [models.UniqueConstraint(fields=["establecimiento", "nivel", "letra", "anio"],
                                               name="curso_unico_por_establecimiento")]

    def __str__(self):
        return f"{self.nivel} {self.letra} ({self.anio})"

    @property
    def nombre_corto(self):
        return f"{self.nivel} {self.letra}"

    @property
    def decreto_plan(self):
        return self.decreto_plan_estudios or self.nivel.decreto_plan_estudios

    @property
    def descripcion_modalidad(self):
        if self.modalidad == self.Modalidad.TP and self.especialidad:
            return f"TP · {self.especialidad}" + (f" (mención {self.mencion})" if self.mencion else "")
        return self.get_modalidad_display()


class Religion(models.TextChoices):
    CATOLICA = "CATOLICA", "Católica"
    EVANGELICA = "EVANGELICA", "Evangélica"
    NO_OPTA = "NO_OPTA", "No opta (eximido de Religión)"


class Asignatura(DeEstablecimiento):
    class Tipo(models.TextChoices):
        ASIGNATURA = "ASIGNATURA", "Asignatura del plan de estudios"
        DIFERENCIADA = "DIFERENCIADA", "Plan diferenciado HC (electivo)"
        MODULO_TP = "MODULO_TP", "Módulo de especialidad TP"
        TALLER = "TALLER", "Taller JEC"

    nombre = models.CharField(max_length=100)
    codigo = models.CharField("código", max_length=20, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ASIGNATURA)
    incide_en_promedio = models.BooleanField(
        "incide en el promedio y la promoción", default=True,
        help_text="Desmarcar para Religión u Orientación (Decreto 67/2018).")
    con_concepto = models.BooleanField(
        "se informa con concepto", default=False,
        help_text="Marcar si en los informes se muestra concepto (MB, B, S, I) en vez de nota.")
    religion = models.CharField(
        "credo", max_length=20, choices=[c for c in Religion.choices if c[0] != "NO_OPTA"], blank=True,
        help_text="Solo para Religión: la cursan únicamente los estudiantes de este credo.")

    class Meta:
        ordering = ["orden", "nombre"]
        constraints = [models.UniqueConstraint(fields=["establecimiento", "nombre"],
                                               name="asignatura_unica_por_establecimiento")]

    def __str__(self):
        return self.nombre


class AsignaturaCurso(models.Model):
    """Carga académica: qué asignatura se dicta en qué curso y quién la dicta."""
    objects = PorEstablecimientoManager.por("curso__establecimiento")
    todos = models.Manager()


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


class Estudiante(DeEstablecimiento):
    rut = models.CharField("RUT", max_length=15, validators=[validar_rut])
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
    religion = models.CharField("clase de Religión", max_length=20, choices=Religion.choices, blank=True,
                                help_text="Según la encuesta de opción de Religión que firma el apoderado.")
    porcentaje_asistencia = models.DecimalField(
        "% de asistencia", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Asistencia anual; se puede cargar desde la nómina SIGE.")
    activo = models.BooleanField(default=True, help_text="Desmarcar si el estudiante se retiró")

    class Meta:
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]
        constraints = [models.UniqueConstraint(fields=["establecimiento", "rut"],
                                               name="estudiante_rut_unico_por_establecimiento")]

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

    def cursa(self, asignatura):
        """False si la asignatura es Religión de otro credo (o el estudiante no opta por Religión)."""
        return not asignatura.religion or self.religion == asignatura.religion

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut)


class Evaluacion(models.Model):
    objects = PorEstablecimientoManager.por("asignatura_curso__curso__establecimiento")
    todos = models.Manager()

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
    objects = PorEstablecimientoManager.por("estudiante__establecimiento")
    todos = models.Manager()

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


class OpcionCatalogo(DeEstablecimiento):
    """Listas editables por el establecimiento (protocolos de convivencia, redes de apoyo externas)."""

    class Tipo(models.TextChoices):
        PROTOCOLO = "PROTOCOLO", "Protocolo de convivencia"
        RED = "RED", "Institución o red de apoyo externa"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=150)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True, help_text="Desmarque para dejar de ofrecerla (se conserva en los registros).")

    class Meta:
        verbose_name = "opción de lista"
        verbose_name_plural = "listas editables"
        ordering = ["tipo", "orden", "nombre"]
        unique_together = [("establecimiento", "tipo", "codigo")]

    def __str__(self):
        return self.nombre

    @classmethod
    def nombres(cls, tipo):
        return dict(cls.objects.filter(tipo=tipo).values_list("codigo", "nombre"))

    @classmethod
    def opciones(cls, tipo, actual=""):
        qs = cls.objects.filter(tipo=tipo)
        return [(o.codigo, o.nombre) for o in qs if o.activo or o.codigo == actual]

    @classmethod
    def nuevo_codigo(cls, tipo, nombre):
        from django.utils.text import slugify

        base = (slugify(nombre).replace("-", "_").upper() or "OPCION")[:24]
        codigo, n = base, 2
        while cls.objects.filter(tipo=tipo, codigo=codigo).exists():
            codigo, n = f"{base}_{n}", n + 1
        return codigo


def _nombre_catalogo(tipo, codigo):
    if not codigo:
        return ""
    return OpcionCatalogo.nombres(tipo).get(codigo, codigo.replace("_", " ").capitalize())


class EstadoDerivacion(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente de revisión"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    CERRADA = "CERRADA", "Cerrada"


class Anotacion(models.Model):
    objects = PorEstablecimientoManager.por("estudiante__establecimiento")
    todos = models.Manager()

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
    # Derivación a Convivencia Escolar (datos sensibles)
    derivada = models.BooleanField("derivada a Convivencia Escolar", default=False)
    protocolo = models.CharField("protocolo activado", max_length=30, blank=True)
    estado_derivacion = models.CharField("estado de la derivación", max_length=20, choices=EstadoDerivacion.choices,
                                         blank=True)
    seguimiento = models.TextField("seguimiento de Convivencia", blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    def get_protocolo_display(self):
        return _nombre_catalogo(OpcionCatalogo.Tipo.PROTOCOLO, self.protocolo)

    # Sugerencia: según el Reglamento Interno, las faltas graves y gravísimas se derivan a Convivencia
    GRAVEDADES_QUE_SE_DERIVAN = ("GRAVE", "GRAVISIMA")

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
    objects = PorEstablecimientoManager.por("estudiante__establecimiento")
    todos = models.Manager()


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


class Comentario(DeEstablecimiento):
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


class Funcionario(DeEstablecimiento):
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
    rut = models.CharField("RUT", max_length=15, validators=[validar_rut])
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
        constraints = [models.UniqueConstraint(fields=["establecimiento", "rut"],
                                               name="funcionario_rut_unico_por_establecimiento")]

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


class RedApoyo(models.Model):
    """Programa o institución externa que atiende al estudiante (dato sensible)."""
    objects = PorEstablecimientoManager.por("estudiante__establecimiento")
    todos = models.Manager()


    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="redes_apoyo")
    institucion = models.CharField("institución", max_length=30)
    programa = models.CharField("programa o detalle", max_length=150, blank=True,
                                help_text="Ej.: PPF Chillán, PIE, PRM, DAM, residencia, causa RIT P-123-2026.")
    profesional = models.CharField("profesional de contacto", max_length=150, blank=True)
    telefono = models.CharField("teléfono / correo de contacto", max_length=100, blank=True)
    fecha_inicio = models.DateField("desde", null=True, blank=True)
    fecha_termino = models.DateField("hasta", null=True, blank=True)
    vigente = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "red de apoyo externa"
        verbose_name_plural = "redes de apoyo externas"
        ordering = ["-vigente", "-fecha_inicio", "-creada"]

    def get_institucion_display(self):
        return _nombre_catalogo(OpcionCatalogo.Tipo.RED, self.institucion)

    def __str__(self):
        return f"{self.get_institucion_display()} – {self.estudiante}"


class Entrevista(models.Model):
    """Registro de entrevista (apoderado/a, estudiante o activación de protocolo)."""
    objects = PorEstablecimientoManager.por("estudiante__establecimiento")
    todos = models.Manager()


    class Tipo(models.TextChoices):
        APODERADO = "APODERADO", "Entrevista con apoderado(a)"
        ESTUDIANTE = "ESTUDIANTE", "Entrevista con estudiante"
        PROTOCOLO = "PROTOCOLO", "Activación de protocolo"
        OTRA = "OTRA", "Otra entrevista"

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="entrevistas")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.APODERADO)
    fecha = models.DateField(default=timezone.localdate)
    hora = models.TimeField(null=True, blank=True)
    anotacion = models.ForeignKey(Anotacion, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="entrevistas", verbose_name="anotación relacionada")
    protocolo = models.CharField("protocolo", max_length=30, blank=True)
    entrevistado = models.CharField("nombre de la persona entrevistada", max_length=150, blank=True)
    parentesco = models.CharField("parentesco o relación con el estudiante", max_length=80, blank=True)
    rut_entrevistado = models.CharField("RUT de la persona entrevistada", max_length=15, blank=True)
    otros_asistentes = models.CharField("otros asistentes", max_length=250, blank=True)
    motivo = models.TextField("motivo de la entrevista")
    desarrollo = models.TextField("desarrollo / relato", blank=True,
                                  help_text="Registre los hechos de forma objetiva, con las palabras de los participantes.")
    acuerdos = models.TextField("acuerdos", blank=True)
    compromisos_apoderado = models.TextField("compromisos del apoderado(a)", blank=True)
    compromisos_estudiante = models.TextField("compromisos del estudiante", blank=True)
    compromisos_establecimiento = models.TextField("compromisos del establecimiento", blank=True)
    derivaciones = models.TextField("derivaciones realizadas", blank=True,
                                    help_text="Ej.: derivación a OLN, denuncia a Fiscalía/Carabineros/PDI, CESFAM.")
    fecha_seguimiento = models.DateField("fecha de seguimiento", null=True, blank=True)
    entrevistador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                      related_name="entrevistas_realizadas")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entrevista"
        verbose_name_plural = "entrevistas"
        ordering = ["-fecha", "-creada"]

    def get_protocolo_display(self):
        return _nombre_catalogo(OpcionCatalogo.Tipo.PROTOCOLO, self.protocolo)

    def __str__(self):
        return f"{self.get_tipo_display()} – {self.estudiante} ({self.fecha:%d-%m-%Y})"


@receiver(post_save, sender=Establecimiento)
def _nuevo_establecimiento(sender, instance, created, raw=False, **kwargs):
    """Cada establecimiento nuevo parte con las listas de protocolos y redes por defecto."""
    if created and not raw:
        from .catalogos import sembrar_catalogos
        sembrar_catalogos(instance)


# --------------------------------------------------------------------------- Libro de clases digital

class Clase(models.Model):
    """Una clase del libro de clases: planificación (leccionario), registro, asistencia y firma del docente."""
    objects = PorEstablecimientoManager.por("asignatura_curso__curso__establecimiento")
    todos = models.Manager()

    asignatura_curso = models.ForeignKey(AsignaturaCurso, on_delete=models.CASCADE, related_name="clases")
    fecha = models.DateField(default=timezone.localdate)
    hora_inicio = models.TimeField("hora de inicio", null=True, blank=True)
    bloques = models.PositiveSmallIntegerField("horas pedagógicas", default=2)
    unidad = models.CharField("unidad", max_length=200, blank=True)
    objetivo = models.TextField("objetivo de aprendizaje (OA)", help_text="Ej.: OA 3 – Leer y comprender textos…")
    actividades = models.TextField(
        "contenidos y actividades", blank=True,
        help_text="Inicio, desarrollo y cierre de la clase. Al planificar se escribe lo previsto; al registrar, lo realizado.")
    recursos = models.CharField("recursos", max_length=250, blank=True)
    observaciones = models.TextField(blank=True)
    evaluacion = models.OneToOneField(Evaluacion, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="clase", verbose_name="evaluación de esta clase")
    oas = models.ManyToManyField("ObjetivoAprendizaje", blank=True, related_name="clases",
                                 verbose_name="OA del currículum nacional")
    asistencia_registrada = models.BooleanField(default=False)
    firmada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="clases_firmadas")
    firmada_en = models.DateTimeField(null=True, blank=True)
    visado_utp = models.TextField("observación de UTP", blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "clase"
        verbose_name_plural = "libro de clases"
        ordering = ["fecha", "hora_inicio", "id"]

    def __str__(self):
        return f"{self.asignatura_curso} · {self.fecha:%d-%m-%Y}"

    @property
    def firmada(self):
        return self.firmada_en is not None

    @property
    def estado(self):
        if self.firmada:
            return "Firmada"
        if self.asistencia_registrada:
            return "Realizada (sin firma)"
        return "Planificada"


class AsistenciaClase(models.Model):
    objects = PorEstablecimientoManager.por("clase__asignatura_curso__curso__establecimiento")
    todos = models.Manager()

    class Estado(models.TextChoices):
        PRESENTE = "P", "Presente"
        AUSENTE = "A", "Ausente"
        ATRASO = "T", "Atrasado(a)"
        RETIRADO = "R", "Retirado(a) antes del término"

    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="asistencias")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="asistencias_clase")
    estado = models.CharField(max_length=1, choices=Estado.choices, default=Estado.PRESENTE)

    class Meta:
        verbose_name = "asistencia a clase"
        verbose_name_plural = "asistencia a clases"
        constraints = [models.UniqueConstraint(fields=["clase", "estudiante"], name="asistencia_unica")]


ASIGNATURAS_CURRICULUM = [
    ("lenguaje", "Lenguaje y Comunicación / Lengua y Literatura"),
    ("matematica", "Matemática"),
    ("ciencias", "Ciencias Naturales"),
    ("historia", "Historia, Geografía y Ciencias Sociales"),
    ("ingles", "Inglés"),
    ("artes", "Artes Visuales"),
    ("musica", "Música"),
    ("educacion_fisica", "Educación Física y Salud"),
    ("tecnologia", "Tecnología"),
    ("orientacion", "Orientación"),
    ("religion", "Religión"),
    ("otra", "Otra / módulo o taller"),
]
GRADOS_CURRICULUM = [(g, f"{g}° básico") for g in range(1, 9)] + [
    (9, "I medio"), (10, "II medio"), (11, "III medio"), (12, "IV medio")]


class ObjetivoAprendizaje(models.Model):
    """OA del currículum nacional. Los oficiales (sin establecimiento) los comparten todos los establecimientos;
    cada establecimiento puede agregar los suyos (programas propios, talleres, módulos TP)."""
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, null=True, blank=True,
                                        editable=False, related_name="objetivos")
    asignatura = models.CharField(max_length=20, choices=ASIGNATURAS_CURRICULUM)
    grado = models.PositiveSmallIntegerField("nivel", choices=GRADOS_CURRICULUM)
    numero = models.PositiveSmallIntegerField("N° de OA")
    texto = models.TextField("objetivo de aprendizaje")
    basal = models.BooleanField("aprendizaje basal (priorización)", default=False)
    unidad = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "objetivo de aprendizaje"
        verbose_name_plural = "objetivos de aprendizaje"
        ordering = ["asignatura", "grado", "numero"]
        constraints = [models.UniqueConstraint(fields=["establecimiento", "asignatura", "grado", "numero"],
                                               name="oa_unico")]

    def __str__(self):
        return f"OA {self.numero}: {self.texto}"

    @property
    def codigo(self):
        return f"OA {self.numero}"

    @classmethod
    def disponibles(cls):
        est = Establecimiento.actual()
        return cls.objects.filter(models.Q(establecimiento__isnull=True) | models.Q(establecimiento_id=est.pk))
