from django import forms

from .models import Anotacion, Asignatura, Entrevista, Estudiante, Evaluacion, Funcionario, RedApoyo
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
