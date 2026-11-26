"""Reglas de acceso.

- Director(a) y Jefe(a) de UTP ("gestión") ven y editan todo: todos los niveles y cursos.
- Un profesor(a) ve solo las asignaturas que dicta (y edita sus notas).
- Un profesor(a) jefe además puede consultar (sin editar) todas las notas de su curso
  y emitir sus informes.
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


def rol_de(user) -> str:
    if user.is_superuser:
        return Perfil.Rol.DIRECTOR
    perfil = getattr(user, "perfil", None)
    return perfil.rol if perfil else Perfil.Rol.PROFESOR


def cursos_visibles(user):
    if es_gestion(user):
        return Curso.objects.all()
    return Curso.objects.filter(Q(asignaturas_curso__profesor=user) | Q(profesor_jefe=user)).distinct()


def asignaturas_curso_visibles(user):
    qs = AsignaturaCurso.objects.select_related("curso__nivel", "asignatura", "profesor")
    if es_gestion(user):
        return qs
    return qs.filter(Q(profesor=user) | Q(curso__profesor_jefe=user))


def estudiantes_visibles(user):
    if es_gestion(user):
        return Estudiante.objects.all()
    return Estudiante.objects.filter(curso__in=cursos_visibles(user))


def puede_ver_curso(user, curso) -> bool:
    return cursos_visibles(user).filter(pk=curso.pk).exists()


def puede_ver_asignatura_curso(user, ac) -> bool:
    return es_gestion(user) or ac.profesor_id == user.id or ac.curso.profesor_jefe_id == user.id


def puede_editar_notas(user, ac) -> bool:
    return es_gestion(user) or ac.profesor_id == user.id


def puede_ver_informe_curso(user, curso) -> bool:
    """Informes completos del curso (todas las asignaturas): gestión o profesor jefe."""
    return es_gestion(user) or curso.profesor_jefe_id == user.id


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
