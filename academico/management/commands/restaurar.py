from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from academico import respaldos


class Command(BaseCommand):
    help = "Restaura un respaldo. Sin argumentos, muestra la lista numerada de respaldos."

    def add_arguments(self, parser):
        parser.add_argument("respaldo", nargs="?", help="Número de la lista o ruta del archivo .zip")
        parser.add_argument("--si", action="store_true", help="No pedir confirmación.")

    def handle(self, *args, **op):
        lista = respaldos.listar()
        if not op["respaldo"]:
            if not lista:
                self.stdout.write("No hay respaldos en la carpeta de respaldos.")
            for i, r in enumerate(lista, start=1):
                self.stdout.write(f"  {i:>3}. {r.fecha:%d-%m-%Y %H:%M}   {r.nombre}")
            return
        valor = op["respaldo"].strip().strip('"')
        if valor.isdigit():
            n = int(valor)
            if not 1 <= n <= len(lista):
                raise CommandError("Número fuera de la lista.")
            archivo = lista[n - 1].ruta
        else:
            archivo = Path(valor)
            if not archivo.exists():
                raise CommandError(f"No existe el archivo {archivo}")
        if not op["si"]:
            resp = input(f"Se reemplazarán los datos actuales por el respaldo {archivo.name}. ¿Continuar? (s/n): ")
            if resp.strip().lower() not in ("s", "si", "sí"):
                self.stdout.write("Cancelado. No se cambió nada.")
                return
        try:
            seguridad = respaldos.restaurar(archivo)
        except respaldos.ErrorRespaldo as e:
            raise CommandError(str(e))
        if seguridad:
            self.stdout.write(f"Antes de restaurar se guardó una copia de los datos anteriores: {seguridad.nombre}")
        self.stdout.write(self.style.SUCCESS(f"Respaldo {archivo.name} restaurado correctamente."))
