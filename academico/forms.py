from decimal import Decimal

from django import forms

from .models import (
    Anotacion, Asignatura, Clase, Entrevista, Establecimiento, Estudiante, Evaluacion, Funcionario, ObjetivoAprendizaje, OpcionCatalogo, RedApoyo,
)
from .lectores import EXTENSIONES
from .rut import normalizar_rut, validar_rut


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class EstudianteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "rut", "nombres", "apellido_paterno", "apellido_materno", "fecha_nacimiento", "genero", "curso", "religion",
            "direccion", "comuna", "codigo_comuna", "telefono", "celular", "email",
            "apoderado_nombre", "apoderado_rut", "apoderado_telefono",
            "contacto_emergencia", "telefono_emergencia", "codigo_etnia", "fecha_incorporacion",
            "porcentaje_asistencia", "fecha_retiro", "activo",
        ]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "fecha_incorporacion": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "fecha_retiro": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        existe = Estudiante.objects.filter(rut=rut).exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Ya existe un estudiante con este RUT.")
        return rut



def _campo_catalogo(form, nombre, tipo, obligatorio=False):
    """Convierte un campo de texto en una lista desplegable con las opciones editables del establecimiento."""
    actual = getattr(form.instance, nombre, "") or form.initial.get(nombre, "")
    vacio = [] if obligatorio else [("", "— Ninguno —")]
    campo = forms.ChoiceField(label=form.fields[nombre].label, required=obligatorio,
                              choices=vacio + OpcionCatalogo.opciones(tipo, actual),
                              help_text=form.fields[nombre].help_text)
    campo.widget.attrs["class"] = "form-select"
    form.fields[nombre] = campo

class AnotacionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Anotacion
        fields = ["fecha", "tipo", "gravedad", "asignatura", "descripcion", "medida", "derivada"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "medida": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {"derivada": "Las faltas graves y gravísimas se derivan automáticamente."}

    def __init__(self, *args, asignaturas=None, **kwargs):
        super().__init__(*args, **kwargs)
        if asignaturas is not None:
            self.fields["asignatura"].queryset = asignaturas

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") != Anotacion.Tipo.NEGATIVA:
            datos["gravedad"] = ""
        if datos.get("gravedad") in Anotacion.GRAVEDADES_QUE_SE_DERIVAN:
            datos["derivada"] = True
        return datos

    def save(self, commit=True):
        anotacion = super().save(commit=False)
        if anotacion.derivada and not anotacion.estado_derivacion:
            anotacion.estado_derivacion = "PENDIENTE"
        if commit:
            anotacion.save()
        return anotacion


class DerivacionForm(BootstrapMixin, forms.ModelForm):
    """Convivencia Escolar registra la gestión de una anotación derivada."""

    class Meta:
        model = Anotacion
        fields = ["derivada", "estado_derivacion", "protocolo", "seguimiento"]
        widgets = {"seguimiento": forms.Textarea(attrs={"rows": 5})}
        help_texts = {"protocolo": "Deje vacío si no fue necesario activar un protocolo."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _campo_catalogo(self, "protocolo", OpcionCatalogo.Tipo.PROTOCOLO)

    def clean(self):
        datos = super().clean()
        if datos.get("derivada") and not datos.get("estado_derivacion"):
            datos["estado_derivacion"] = "PENDIENTE"
        if not datos.get("derivada"):
            datos["estado_derivacion"], datos["protocolo"] = "", ""
        return datos


_FECHA = {"type": "date"}


class RedApoyoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = RedApoyo
        fields = ["institucion", "programa", "profesional", "telefono", "fecha_inicio", "fecha_termino", "vigente",
                  "observaciones"]
        widgets = {"fecha_inicio": forms.DateInput(attrs=_FECHA, format="%Y-%m-%d"),
                   "fecha_termino": forms.DateInput(attrs=_FECHA, format="%Y-%m-%d"),
                   "observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _campo_catalogo(self, "institucion", OpcionCatalogo.Tipo.RED, obligatorio=True)


class EntrevistaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Entrevista
        fields = ["tipo", "fecha", "hora", "protocolo", "anotacion", "entrevistado", "parentesco", "rut_entrevistado",
                  "otros_asistentes", "motivo", "desarrollo", "acuerdos", "compromisos_apoderado",
                  "compromisos_estudiante", "compromisos_establecimiento", "derivaciones", "fecha_seguimiento"]
        widgets = {
            "fecha": forms.DateInput(attrs=_FECHA, format="%Y-%m-%d"),
            "fecha_seguimiento": forms.DateInput(attrs=_FECHA, format="%Y-%m-%d"),
            "hora": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            **{c: forms.Textarea(attrs={"rows": 3}) for c in (
                "motivo", "acuerdos", "compromisos_apoderado", "compromisos_estudiante",
                "compromisos_establecimiento", "derivaciones")},
            "desarrollo": forms.Textarea(attrs={"rows": 7}),
        }

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        _campo_catalogo(self, "protocolo", OpcionCatalogo.Tipo.PROTOCOLO)
        self.fields["anotacion"].queryset = estudiante.anotaciones.all() if estudiante else Anotacion.objects.none()
        self.fields["anotacion"].label_from_instance = lambda a: (
            f"{a.fecha:%d-%m-%Y} · {a.get_tipo_display()}{' ' + a.get_gravedad_display() if a.gravedad else ''}: "
            f"{a.descripcion[:60]}")

    def clean_rut_entrevistado(self):
        rut = self.cleaned_data.get("rut_entrevistado", "").strip()
        if rut:
            validar_rut(rut)
            rut = normalizar_rut(rut)
        return rut


class EvaluacionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Evaluacion
        fields = ["nombre", "fecha", "semestre", "ponderacion"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ArchivoExcelForm(BootstrapMixin, forms.Form):
    archivo = forms.FileField(
        label="Archivo (Excel, CSV, Word o nómina SIGE)",
        widget=forms.ClearableFileInput(attrs={"accept": ",".join(EXTENSIONES)}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(EXTENSIONES):
            raise forms.ValidationError(
                "Formato no aceptado. Use Excel (.xlsx o .xls), CSV, Word (.docx) o la nómina exportada desde SIGE.")
        return archivo


CAMPOS_SOLICITABLES = [
    "rut", "nombres", "apellido_paterno", "apellido_materno", "fecha_nacimiento",
    "direccion", "comuna", "telefono", "celular", "email",
    "apoderado_nombre", "apoderado_rut", "apoderado_telefono",
    "contacto_emergencia", "telefono_emergencia",
]


class SolicitudCambioForm(EstudianteForm):
    """Mismos datos del estudiante (sin curso ni estado) más el motivo del cambio."""

    motivo = forms.CharField(label="Motivo de la solicitud", widget=forms.Textarea(attrs={"rows": 2}),
                             required=True)

    class Meta(EstudianteForm.Meta):
        fields = CAMPOS_SOLICITABLES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Al validar, Django copia los datos al estudiante en memoria: guardamos los originales antes.
        self.originales = {c: getattr(self.instance, c) for c in CAMPOS_SOLICITABLES}

    def cambios(self):
        """Diferencias entre lo enviado y los datos actuales del estudiante."""
        resultado = {}
        for campo in CAMPOS_SOLICITABLES:
            antes = self.originales[campo]
            despues = self.cleaned_data.get(campo)
            if (antes or "") != (despues or ""):
                resultado[campo] = {"antes": _serializar(antes), "despues": _serializar(despues)}
        return resultado


def _serializar(valor):
    if valor in (None, ""):
        return ""
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


class ContactoEstudianteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ["direccion", "comuna", "telefono", "celular", "email", "apoderado_nombre", "apoderado_rut",
                  "apoderado_telefono", "contacto_emergencia", "telefono_emergencia"]


class FuncionarioForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = ["rut", "nombres", "apellido_paterno", "apellido_materno", "cargo", "titulo", "mencion",
                  "tipo_contrato", "horas_contrato", "primer_ciclo", "proporcion", "fecha_ingreso",
                  "tramo", "anios_experiencia", "brp_mencion", "evaluacion_docente", "evaluacion_anio",
                  "telefono", "email", "usuario", "activo"]
        widgets = {"fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        if Funcionario.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un funcionario con este RUT.")
        return rut


class AgregarAsignaturaCursoForm(BootstrapMixin, forms.Form):
    """Agrega una asignatura del plan o un taller JEC a la carga académica de un curso."""
    asignatura = forms.ModelChoiceField(label="Asignatura o taller existente", queryset=None, required=False,
                                        empty_label="— Elegir —")
    nuevo_taller = forms.CharField(label="…o crear un taller JEC nuevo", max_length=100, required=False,
                                   help_text="Ej.: Taller de Ajedrez. Déjelo vacío si eligió una asignatura arriba.")
    profesor = forms.ModelChoiceField(label="Profesor(a)", queryset=None, required=False, empty_label="Sin asignar")
    horas_semanales = forms.DecimalField(label="Horas semanales", max_digits=4, decimal_places=1, min_value=0,
                                         required=False)
    incide_en_promedio = forms.BooleanField(
        label="La nota del taller incide en el promedio", required=False, initial=True,
        help_text="Solo para talleres nuevos. Los talleres se califican con nota.")
    todo_el_nivel = forms.BooleanField(label="Agregar también a los otros cursos del mismo nivel", required=False)

    def __init__(self, *args, curso=None, profesores=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.curso = curso
        self.fields["asignatura"].queryset = Asignatura.objects.exclude(cursos__curso=curso).order_by(
            "tipo", "orden", "nombre")
        self.fields["asignatura"].label_from_instance = lambda a: (
            f"{a.nombre} (taller JEC)" if a.tipo == Asignatura.Tipo.TALLER else a.nombre)
        self.fields["profesor"].queryset = profesores
        self.fields["profesor"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean(self):
        datos = super().clean()
        nombre = (datos.get("nuevo_taller") or "").strip()
        if bool(datos.get("asignatura")) == bool(nombre):
            raise forms.ValidationError("Elija una asignatura existente o escriba el nombre de un taller nuevo (solo una).")
        if nombre:
            existente = Asignatura.objects.filter(nombre__iexact=nombre).first()
            if existente and existente.tipo != Asignatura.Tipo.TALLER:
                raise forms.ValidationError(f"«{existente}» ya existe como asignatura del plan: elíjala en la lista.")
            datos["nuevo_taller"] = nombre
        return datos


class PrimeraConfiguracionForm(BootstrapMixin, forms.Form):
    """Asistente de la primera vez: datos de la escuela y la cuenta de quien administra la plataforma."""
    nombre = forms.CharField(label="Nombre del establecimiento", max_length=200)
    rbd = forms.CharField(label="RBD", max_length=20, required=False)
    comuna = forms.CharField(max_length=100, required=False)
    region = forms.CharField(label="Región", max_length=100, required=False, help_text="Ej.: Ñuble")
    director = forms.CharField(label="Nombre del director(a)", max_length=200, required=False)
    jefe_utp = forms.CharField(label="Nombre del jefe(a) de UTP", max_length=200, required=False)
    rol = forms.ChoiceField(label="Su cargo", choices=[("DIRECTOR", "Director(a)"), ("UTP", "Jefe(a) de UTP")])
    nombres = forms.CharField(label="Sus nombres", max_length=150)
    apellidos = forms.CharField(label="Sus apellidos", max_length=150)
    usuario = forms.RegexField(label="Nombre de usuario para ingresar", max_length=150, regex=r"^[a-zA-Z0-9._-]+$",
                               help_text="Sin espacios ni tildes. Ej.: jsandoval",
                               error_messages={"invalid": "Use solo letras sin tilde, números, punto, guion o guion bajo."})
    clave1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    clave2 = forms.CharField(label="Repita la contraseña", widget=forms.PasswordInput)
    plan_oficial = forms.BooleanField(label="Crear las asignaturas del plan oficial de Enseñanza Básica",
                                      required=False, initial=True)

    def clean(self):
        from django.contrib.auth.password_validation import validate_password

        datos = super().clean()
        if datos.get("clave1") != datos.get("clave2"):
            self.add_error("clave2", "Las contraseñas no coinciden.")
        elif datos.get("clave1"):
            try:
                validate_password(datos["clave1"])
            except forms.ValidationError as e:
                self.add_error("clave1", e)
        return datos


class ConfiguracionEstablecimientoForm(BootstrapMixin, forms.ModelForm):
    logo_archivo = forms.ImageField(label="Logo institucional", required=False,
                                    help_text="PNG o JPG. Aparece en el menú, la pantalla de ingreso, las planillas Excel "
                                              "y las entrevistas. Los documentos oficiales Mineduc no lo llevan.")
    quitar_logo = forms.BooleanField(label="Quitar el logo actual", required=False)

    class Meta:
        model = Establecimiento
        fields = ["nombre", "rbd", "direccion", "comuna", "region", "telefono", "director", "jefe_utp",
                  "resolucion_reconocimiento", "alta_concentracion", "conceptos_basica", "hora_asistencia", "asistente_ia", "color_principal",
                  "pie_documentos"]
        widgets = {"color_principal": forms.TextInput(attrs={"type": "color"}),
                   "hora_asistencia": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color_principal"].widget.attrs["class"] = "form-control form-control-color"
        self.fields["hora_asistencia"].required = False
        if not self.instance.color_principal:
            self.initial["color_principal"] = "#24476B"

    def clean_hora_asistencia(self):
        import datetime
        return self.cleaned_data.get("hora_asistencia") or self.instance.hora_asistencia or datetime.time(10, 0)

    def clean_color_principal(self):
        import re
        color = (self.cleaned_data.get("color_principal") or "").strip()
        if color.upper() == "#24476B":
            return ""
        if color and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise forms.ValidationError("Color no válido.")
        return color

    def clean_logo_archivo(self):
        archivo = self.cleaned_data.get("logo_archivo")
        if not archivo:
            return None
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("El logo debe pesar menos de 5 MB.")
        from io import BytesIO

        from PIL import Image
        try:
            img = Image.open(archivo)
            img.load()
        except Exception:
            raise forms.ValidationError("No se pudo leer la imagen. Use un archivo PNG o JPG.")
        img = img.convert("RGBA")
        img.thumbnail((600, 600))
        salida = BytesIO()
        img.save(salida, format="PNG", optimize=True)
        return salida.getvalue()

    def save(self, commit=True):
        est = super().save(commit=False)
        if self.cleaned_data.get("quitar_logo"):
            est.logo = None
        elif self.cleaned_data.get("logo_archivo"):
            est.logo = self.cleaned_data["logo_archivo"]
        if commit:
            est.save()
        return est


class ClaseForm(BootstrapMixin, forms.ModelForm):
    """Planificación / registro de una clase del leccionario."""
    es_evaluacion = forms.BooleanField(
        label="En esta clase se aplica una evaluación con nota", required=False,
        help_text="Crea la evaluación en el libro de notas de la asignatura, con la fecha de la clase.")
    nombre_evaluacion = forms.CharField(label="Nombre de la evaluación", max_length=100, required=False,
                                        help_text="Ej.: Prueba Unidad 2, Disertación, Control de lectura.")
    ponderacion = forms.DecimalField(label="Ponderación", max_digits=5, decimal_places=2, required=False,
                                     min_value=Decimal("0.01"), initial=Decimal("1"),
                                     help_text="Peso dentro del semestre (1 = todas pesan igual).")

    class Meta:
        model = Clase
        fields = ["fecha", "hora_inicio", "bloques", "unidad", "oas", "objetivo", "actividades", "recursos",
                  "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "objetivo": forms.Textarea(attrs={"rows": 2}),
            "actividades": forms.Textarea(attrs={"rows": 5}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "oas": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, oas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["oas"].queryset = oas if oas is not None else self.fields["oas"].queryset.none()
        self.fields["oas"].widget.attrs["class"] = "form-check-input"
        self.fields["oas"].label = "OA del currículum nacional que trabaja esta clase"
        ev = self.instance.evaluacion if self.instance.pk else None
        if ev:
            self.fields["es_evaluacion"].initial = True
            self.fields["nombre_evaluacion"].initial = ev.nombre
            self.fields["ponderacion"].initial = ev.ponderacion

    def clean(self):
        datos = super().clean()
        if datos.get("es_evaluacion") and not (datos.get("nombre_evaluacion") or "").strip():
            self.add_error("nombre_evaluacion", "Indique el nombre de la evaluación.")
        return datos


class VisadoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Clase
        fields = ["visado_utp"]
        widgets = {"visado_utp": forms.Textarea(attrs={"rows": 2})}


class ObjetivoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ObjetivoAprendizaje
        fields = ["asignatura_propia", "asignatura", "grado", "numero", "texto", "unidad"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Asignatura
        campo = self.fields["asignatura_propia"]
        campo.queryset = Asignatura.objects.order_by("tipo", "nombre")
        campo.label_from_instance = lambda a: f"{a.nombre} ({a.get_tipo_display().split(' (')[0]})"
        campo.empty_label = "— Ninguna: asignatura del currículum nacional —"
        self.fields["asignatura"].required = False
        self.fields["asignatura"].help_text = "Solo si no eligió un taller, módulo o asignatura arriba."

    def clean(self):
        d = super().clean()
        if d.get("asignatura_propia"):
            from .curriculo import clave_asignatura
            d["asignatura"] = clave_asignatura(d["asignatura_propia"].nombre)
            if d["asignatura_propia"].tipo != "ASIGNATURA":
                d["asignatura"] = "otra"
            self.instance.asignatura = d["asignatura"]
        elif not d.get("asignatura"):
            self.add_error("asignatura", "Elija la asignatura del currículum o un taller/módulo del establecimiento.")
        return d


class SimceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        from .models import ResultadoSimce
        model = ResultadoSimce
        fields = ["anio", "nivel", "prueba", "puntaje", "puntaje_nacional", "puntaje_gse", "evaluados",
                  "pct_adecuado", "pct_insuficiente"]


class PaesForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        from .models import ResultadoPaes
        model = ResultadoPaes
        fields = ["anio", "prueba", "puntaje", "puntaje_nacional", "rindieron"]
