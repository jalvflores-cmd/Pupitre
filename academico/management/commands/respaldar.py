from django.core.management.base import BaseCommand, CommandError

from academico import respaldos


class Command(BaseCommand):
    help = "Crea un respaldo de la base de datos en la carpeta de respaldos."

    def add_arguments(self, parser):
        parser.add_argument("--si-corresponde", action="store_true",
                            help="Solo respalda si el último respaldo tiene más de 24 horas.")
        parser.add_argument("--motivo", default="manual")

    def handle(self, *args, **op):
        if op["si_corresponde"] and not respaldos.necesita_respaldo_diario():
            self.stdout.write("Ya hay un respaldo de las últimas 24 horas.")
            return
        try:
            r, advertencias = respaldos.crear(op["motivo"])
        except respaldos.ErrorRespaldo as e:
            raise CommandError(str(e))
        for a in advertencias:
            self.stderr.write(self.style.WARNING(a))
        self.stdout.write(self.style.SUCCESS(f"Respaldo creado: {r.ruta}"))
