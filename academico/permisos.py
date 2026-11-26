"""Reglas de acceso.

- Director(a) y Jefe(a) de UTP ("gestión") ven y editan todo: todos los niveles y cursos,
  configuran la plataforma y aprueban solicitudes de modificación de datos.
- Sostenedor(a): ve todo (cursos, notas, estudiantes, convivencia, informes) en modo solo lectura.
- Inspector(a) general y Encargado(a) de convivencia: ven todos los cursos y notas (sin editar),
  registran y eliminan anotaciones en cualquier curso, importan anotaciones, actualizan los datos
  de contacto de los estudiantes y solicitan cambios de nombre/RUT (que aprueba UTP o Dirección).
- Un profesor(a) ve solo las asignaturas que dicta (y edita sus notas).
- Un profesor(a) jefe además consulta (sin editar) todas las notas de su curso, emite sus informes
  y solicita cambios en los datos de sus estudiantes.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import AsignaturaCurso, Curso, Estudiante, Perfil


def es_gestion(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    return bool(perfil and perfil.es_gestion)


def _perfil(user):
    return getattr(user, "perfil", None) if user.is_authenticated else None


def ve_todo(user) -> bool:
    if es_gestion(user):
        return True
    perfil = _perfil(user)
    return bool(perfil and perfil.ve_todo)


def gestiona_convivencia(user) -> bool:
    if es_gestion(user):
        return True
    perfil = _perfil(user)
    return bool(perfil and perfil.gestiona_convivencia)


def es_solo_lectura(user) -> bool:
    perfil = _perfil(user)
    return bool(perfil and perfil.rol == Perfil.Rol.SOSTENEDOR and not user.is_superuser)


def rol_de(user) -> str:
    if user.is_superuser:
        return Perfil.Rol.DIRECTOR
    perfil = getattr(user, "perfil", None)
    return perfil.rol if perfil else Perfil.Rol.PROFESOR


def cursos_visibles(user):
    if ve_todo(user):
        return Curso.objects.all()
    return Curso.objects.filter(Q(asignaturas_curso__profesor=user) | Q(profesor_jefe=user)).distinct()


def asignaturas_curso_visibles(user):
    qs = AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor")
    if ve_todo(user):
        return qs
    return qs.filter(Q(profesor=user) | Q(curso__profesor_jefe=user))


def estudiantes_visibles(user):
    if ve_todo(user):
        return Estudiante.objects.all()
    return Estudiante.objects.filter(curso__in=cursos_visibles(user))


def puede_ver_curso(user, curso) -> bool:
    return cursos_visibles(user).filter(pk=curso.pk).exists()


def puede_ver_asignatura_curso(user, ac) -> bool:
    return ve_todo(user) or ac.profesor_id == user.id or ac.curso.profesor_jefe_id == user.id


def puede_editar_notas(user, ac) -> bool:
    return es_gestion(user) or ac.profesor_id == user.id


def puede_ver_informe_curso(user, curso) -> bool:
    """Informes completos del curso (todas las asignaturas): gestión o profesor jefe."""
    return ve_todo(user) or curso.profesor_jefe_id == user.id


def puede_solicitar_cambio(user, estudiante) -> bool:
    """Profesor(a) jefe del curso, Inspectoría y Convivencia (Dirección y UTP editan directamente)."""
    if es_gestion(user):
        return False
    if gestiona_convivencia(user):
        return True
    return estudiante.curso_id is not None and estudiante.curso.profesor_jefe_id == user.id


def puede_editar_contacto(user) -> bool:
    """Inspectoría y Convivencia actualizan teléfonos, dirección y apoderado directamente."""
    return gestiona_convivencia(user) and not es_gestion(user)


def puede_anotar(user, estudiante) -> bool:
    return not es_solo_lectura(user) and puede_ver_estudiante(user, estudiante)


def puede_eliminar_anotacion(user, anotacion) -> bool:
    return gestiona_convivencia(user) or anotacion.autor_id == user.id


def puede_ver_estudiante(user, estudiante) -> bool:
    return estudiantes_visibles(user).filter(pk=estudiante.pk).exists()


def solo_gestion(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_gestion(request.user):
            raise PermissionDenied("Solo Dirección y UTP pueden realizar esta acción.")
        return vista(request, *args, **kwargs)

    return envoltura


def exigir(condicion: bool):
    if not condicion:
        raise PermissionDenied("No tiene acceso a esta información.")


def puede_ver_funcionarios(user) -> bool:
    return es_gestion(user) or es_solo_lectura(user)
