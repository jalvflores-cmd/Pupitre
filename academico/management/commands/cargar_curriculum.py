from django.core.management.base import BaseCommand

from academico.curriculo import cargar_oficiales
from academico.models import ObjetivoAprendizaje


class Command(BaseCommand):
    help = "Carga o actualiza los OA oficiales precargados del currículum nacional."

    def handle(self, *args, **opciones):
        nuevos = cargar_oficiales(ObjetivoAprendizaje)
        total = ObjetivoAprendizaje.objects.filter(establecimiento__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(f"Currículum listo: {total} OA oficiales ({nuevos} nuevos)."))
