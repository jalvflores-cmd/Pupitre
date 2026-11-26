from django import forms

from .models import Anotacion, Estudiante, Evaluacion
from .rut import normalizar_rut


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
            "rut", "nombres", "apellido_paterno", "apellido_materno", "fecha_nacimiento", "curso",
            "direccion", "comuna", "telefono", "email",
            "apoderado_nombre", "apoderado_rut", "apoderado_telefono",
            "contacto_emergencia", "telefono_emergencia", "activo",
        ]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        existe = Estudiante.objects.filter(rut=rut).exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Ya existe un estudiante con este RUT.")
        return rut


class AnotacionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Anotacion
        fields = ["fecha", "tipo", "gravedad", "asignatura", "descripcion", "medida"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "medida": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, asignaturas=None, **kwargs):
        super().__init__(*args, **kwargs)
        if asignaturas is not None:
            self.fields["asignatura"].queryset = asignaturas

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") != Anotacion.Tipo.NEGATIVA:
            datos["gravedad"] = ""
        return datos


class EvaluacionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Evaluacion
        fields = ["nombre", "fecha", "semestre", "ponderacion"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ArchivoExcelForm(BootstrapMixin, forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("El archivo debe estar en formato .xlsx (Excel 2007 o superior).")
        return archivo


CAMPOS_SOLICITABLES = [
    "rut", "nombres", "apellido_paterno", "apellido_materno", "fecha_nacimiento",
    "direccion", "comuna", "telefono", "email",
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
