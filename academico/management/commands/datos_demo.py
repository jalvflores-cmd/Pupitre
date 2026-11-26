"""Crea datos de demostración: usuarios, cursos, asignaturas, estudiantes, notas y anotaciones.

Uso: python manage.py datos_demo
Usuarios creados (contraseña: demo1234): director, utp, profe.matematica, profe.lenguaje, profe.ciencias
"""
import random
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Curso, Establecimiento, Estudiante, Evaluacion, Nivel,
    Perfil, anio_actual,
)
from academico.rut import calcular_dv

NOMBRES = ["Sofía", "Benjamín", "Isidora", "Agustín", "Florencia", "Vicente", "Emilia", "Matías", "Antonella",
           "Tomás", "Josefa", "Maximiliano", "Martina", "Joaquín", "Catalina", "Lucas", "Trinidad", "Cristóbal"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores"]


class Command(BaseCommand):
    help = "Carga datos de demostración (no usar en producción con datos reales)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(42)
        anio = anio_actual()
        Establecimiento.objects.get_or_create(nombre="Colegio Demostración", defaults={
            "rbd": "12345-6", "direccion": "Av. Educación 1234", "comuna": "Santiago",
            "director": "Ana Valenzuela Rojas", "jefe_utp": "Pedro Castillo Mena"})

        def usuario(username, nombre, apellido, rol):
            u, creado = User.objects.get_or_create(username=username, defaults={"first_name": nombre, "last_name": apellido})
            if creado:
                u.set_password("demo1234")
                u.save()
            Perfil.objects.update_or_create(usuario=u, defaults={"rol": rol})
            return u

        usuario("director", "Ana", "Valenzuela Rojas", Perfil.Rol.DIRECTOR)
        usuario("utp", "Pedro", "Castillo Mena", Perfil.Rol.UTP)
        mate = usuario("profe.matematica", "Carla", "Núñez Pino", Perfil.Rol.PROFESOR)
        leng = usuario("profe.lenguaje", "Jorge", "Reyes Lagos", Perfil.Rol.PROFESOR)
        cien = usuario("profe.ciencias", "Daniela", "Vergara Toro", Perfil.Rol.PROFESOR)

        asignaturas = {}
        for i, nombre in enumerate(["Lenguaje y Comunicación", "Matemática", "Ciencias Naturales",
                                    "Historia, Geografía y Cs. Sociales", "Inglés", "Educación Física y Salud"]):
            asignaturas[nombre], _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={"orden": i})
        profes = {"Matemática": mate, "Lenguaje y Comunicación": leng, "Ciencias Naturales": cien}

        rut_base = 23_000_000
        for orden, nombre_nivel in enumerate(["5° Básico", "6° Básico", "7° Básico"], start=5):
            nivel, _ = Nivel.objects.get_or_create(nombre=nombre_nivel, defaults={"orden": orden})
            for letra in "AB":
                jefe = [mate, leng, cien][(orden + ord(letra)) % 3]
                curso, _ = Curso.objects.get_or_create(nivel=nivel, letra=letra, anio=anio,
                                                       defaults={"profesor_jefe": jefe})
                acs = []
                for nombre_asig, asig in asignaturas.items():
                    ac, _ = AsignaturaCurso.objects.get_or_create(curso=curso, asignatura=asig,
                                                                  defaults={"profesor": profes.get(nombre_asig)})
                    acs.append(ac)
                ests = []
                for _ in range(12):
                    rut_base += random.randint(1000, 9000)
                    est, _ = Estudiante.objects.get_or_create(rut=f"{rut_base}-{calcular_dv(rut_base)}", defaults={
                        "nombres": random.choice(NOMBRES), "apellido_paterno": random.choice(APELLIDOS),
                        "apellido_materno": random.choice(APELLIDOS), "curso": curso,
                        "fecha_nacimiento": date(anio - orden - 6, random.randint(1, 12), random.randint(1, 28)),
                        "direccion": f"Calle {random.choice(APELLIDOS)} {random.randint(100, 3000)}",
                        "comuna": random.choice(["Santiago", "Ñuñoa", "Maipú", "La Florida"]),
                        "telefono": f"+56 9 {random.randint(1000, 9999)} {random.randint(1000, 9999)}",
                        "apoderado_nombre": f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}",
                        "apoderado_telefono": f"+56 9 {random.randint(1000, 9999)} {random.randint(1000, 9999)}",
                    })
                    ests.append(est)
                for ac in acs:
                    for sem in (1, 2):
                        for n in range(1, 4):
                            ev, _ = Evaluacion.objects.get_or_create(
                                asignatura_curso=ac, nombre=f"Prueba {n}", semestre=sem,
                                defaults={"fecha": date(anio, 3 + n + (sem - 1) * 4, 15)})
                            for est in ests:
                                nota = Decimal(str(round(min(7, max(1, random.gauss(5.4, 1.0))), 1)))
                                Calificacion.objects.get_or_create(evaluacion=ev, estudiante=est, defaults={"nota": nota})
                for est in random.sample(ests, 3):
                    tipo = random.choice([Anotacion.Tipo.POSITIVA, Anotacion.Tipo.NEGATIVA])
                    Anotacion.objects.get_or_create(
                        estudiante=est, descripcion=("Destaca por su participación en clases." if tipo == "POSITIVA"
                                                     else "No trae materiales de trabajo."),
                        defaults={"tipo": tipo, "gravedad": "LEVE" if tipo == "NEGATIVA" else "",
                                  "fecha": date(anio, 5, random.randint(1, 28)), "autor": jefe})
        self.stdout.write(self.style.SUCCESS(
            "Datos de demostración creados. Usuarios: director, utp, profe.matematica, profe.lenguaje, "
            "profe.ciencias (contraseña: demo1234)"))
