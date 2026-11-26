"""Varios establecimientos en una misma plataforma: cada uno ve solo sus datos.

El establecimiento «actual» se fija por petición (middleware) según el usuario que ingresó, o el que eligió el
superadministrador. Los modelos con datos de un establecimiento usan `PorEstablecimientoManager`, que filtra
automáticamente por el establecimiento actual. Sin establecimiento actual (comandos, migraciones, panel del
superadministrador) no se filtra.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

_actual: ContextVar = ContextVar("establecimiento_actual", default=None)


def establecimiento_actual():
    return _actual.get()


def fijar(establecimiento):
    return _actual.set(establecimiento)


def restaurar(token):
    _actual.reset(token)


@contextmanager
def en_establecimiento(establecimiento):
    token = fijar(establecimiento)
    try:
        yield establecimiento
    finally:
        restaurar(token)


class PorEstablecimientoQuerySet(models.QuerySet):
    pass


class PorEstablecimientoManager(models.Manager):
    """Filtra por el establecimiento actual siguiendo `ruta` (p. ej. "estudiante__establecimiento")."""

    ruta = "establecimiento"

    @classmethod
    def por(cls, ruta):
        """Manager que filtra siguiendo otra ruta. Se crea una subclase porque Django reconstruye los
        managers relacionados a partir de la clase (sin argumentos)."""
        return type(f"PorEstablecimientoManager_{ruta}", (cls,), {"ruta": ruta})()

    def get_queryset(self):
        qs = super().get_queryset()
        est = _actual.get()
        if est is not None and getattr(est, "pk", None):
            qs = qs.filter(**{self.ruta: est})
        return qs


def establecimiento_por_defecto():
    """Para objetos nuevos sin establecimiento: el actual, o el único/primero (instalación local)."""
    from .models import Establecimiento

    est = _actual.get()
    if est is not None and est.pk:
        return est
    est = Establecimiento.objects.order_by("pk").first()
    if est is None:
        est = Establecimiento.objects.create(nombre="Establecimiento educacional")
    return est


class DeEstablecimiento(models.Model):
    """Mezcla para modelos que pertenecen directamente a un establecimiento."""

    establecimiento = models.ForeignKey("academico.Establecimiento", on_delete=models.CASCADE, null=True,
                                        blank=True, editable=False, related_name="+")

    objects = PorEstablecimientoManager()
    todos = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.establecimiento_id:
            self.establecimiento = establecimiento_por_defecto()
        super().save(*args, **kwargs)
