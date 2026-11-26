"""Panel de administración: lo usan Director(a) y Jefe(a) de UTP para configurar
usuarios, niveles, cursos, asignaturas y la carga académica (quién dicta qué)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User

from .models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Curso, Establecimiento, Estudiante, Evaluacion, Nivel,
    Comentario, Entrevista, Funcionario, Perfil, RedApoyo, SolicitudCambio,
)
from .permisos import es_gestion


class SoloGestion:
    """Da acceso completo a Dirección y UTP sin tener que configurar permisos de Django."""

    def has_module_permission(self, request):
        return es_gestion(request.user)

    def has_view_permission(self, request, obj=None):
        return es_gestion(request.user)

    def has_add_permission(self, request, *args):
        return es_gestion(request.user)

    def has_change_permission(self, request, obj=None):
        return es_gestion(request.user)

    def has_delete_permission(self, request, obj=None):
        return es_gestion(request.user)


admin.site.has_permission = lambda request: request.user.is_active and es_gestion(request.user)
admin.site.unregister(Group)
admin.site.unregister(User)


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = "Rol en la plataforma"


@admin.register(User)
class UsuarioAdmin(SoloGestion, UserAdmin):
    inlines = [PerfilInline]
    list_display = ("username", "first_name", "last_name", "email", "rol", "is_active")
    list_filter = ("perfil__rol", "is_active")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email")}),
        ("Estado", {"fields": ("is_active", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "first_name", "last_name", "email",
                                                  "password1", "password2")}),
    )
    readonly_fields = ("last_login", "date_joined")

    @admin.display(description="Rol")
    def rol(self, obj):
        if obj.is_superuser:
            return "Administrador"
        perfil = getattr(obj, "perfil", None)
        return perfil.get_rol_display() if perfil else "—"

    def get_inline_instances(self, request, obj=None):
        return super().get_inline_instances(request, obj) if obj else []

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        Perfil.objects.get_or_create(usuario=obj)


@admin.register(Establecimiento)
class EstablecimientoAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("nombre", "rbd", "comuna", "director")

    def has_add_permission(self, request, *args):
        return es_gestion(request.user) and not Establecimiento.objects.exists()


@admin.register(Nivel)
class NivelAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("nombre", "orden")
    list_editable = ("orden",)


class AsignaturaCursoInline(admin.TabularInline):
    model = AsignaturaCurso
    extra = 1
    autocomplete_fields = ("asignatura",)


@admin.register(Curso)
class CursoAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("__str__", "nivel", "letra", "anio", "profesor_jefe")
    list_filter = ("anio", "nivel")
    inlines = [AsignaturaCursoInline]


@admin.register(Asignatura)
class AsignaturaAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("nombre", "tipo", "incide_en_promedio", "orden")
    list_editable = ("orden", "incide_en_promedio")
    list_filter = ("tipo",)
    search_fields = ("nombre", "codigo")


@admin.register(AsignaturaCurso)
class AsignaturaCursoAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("asignatura", "curso", "profesor", "horas_semanales")
    list_filter = ("curso__anio", "curso__nivel", "asignatura__tipo", "asignatura", "profesor")
    list_editable = ("profesor", "horas_semanales")


@admin.register(Estudiante)
class EstudianteAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("rut", "apellido_paterno", "apellido_materno", "nombres", "curso", "activo")
    list_filter = ("activo", "curso__anio", "curso__nivel", "curso")
    search_fields = ("rut", "nombres", "apellido_paterno", "apellido_materno")


@admin.register(Evaluacion)
class EvaluacionAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("nombre", "asignatura_curso", "semestre", "fecha", "ponderacion")
    list_filter = ("semestre", "asignatura_curso__curso")


@admin.register(Calificacion)
class CalificacionAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("estudiante", "evaluacion", "nota")
    list_filter = ("evaluacion__asignatura_curso__curso",)
    search_fields = ("estudiante__rut", "estudiante__apellido_paterno")


@admin.register(Anotacion)
class AnotacionAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("fecha", "estudiante", "tipo", "gravedad", "derivada", "protocolo", "autor")
    list_filter = ("tipo", "gravedad", "derivada", "estado_derivacion", "protocolo", "estudiante__curso")
    search_fields = ("estudiante__rut", "estudiante__apellido_paterno", "descripcion")


@admin.register(SolicitudCambio)
class SolicitudCambioAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("estudiante", "solicitante", "estado", "creada", "revisor")
    list_filter = ("estado",)
    readonly_fields = ("cambios", "creada", "revisada")


@admin.register(Comentario)
class ComentarioAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("creado", "usuario", "tipo", "texto", "revisado")
    list_filter = ("tipo", "revisado")
    list_editable = ("revisado",)


@admin.register(Funcionario)
class FuncionarioAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("rut", "apellido_paterno", "nombres", "cargo", "tipo_contrato", "horas_contrato", "activo")
    list_filter = ("cargo", "tipo_contrato", "activo")
    search_fields = ("rut", "nombres", "apellido_paterno")


@admin.register(RedApoyo)
class RedApoyoAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("estudiante", "institucion", "programa", "vigente", "fecha_inicio")
    list_filter = ("institucion", "vigente")
    search_fields = ("estudiante__rut", "estudiante__apellido_paterno", "programa")


@admin.register(Entrevista)
class EntrevistaAdmin(SoloGestion, admin.ModelAdmin):
    list_display = ("fecha", "estudiante", "tipo", "protocolo", "entrevistado", "entrevistador")
    list_filter = ("tipo", "protocolo")
    search_fields = ("estudiante__rut", "estudiante__apellido_paterno", "entrevistado")
