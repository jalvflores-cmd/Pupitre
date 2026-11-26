"""Crea datos de demostración: usuarios, cursos, asignaturas, estudiantes, notas y anotaciones.

Uso: python manage.py datos_demo
Usuarios creados (contraseña: demo1234): sostenedor, director, utp, inspector, convivencia,
profe.historia (profesor de asignatura), profe.matematica, profe.lenguaje, profe.ciencias (además profesores jefe)
"""
import random
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Curso, Establecimiento, Estudiante, Evaluacion, Funcionario,
    Nivel,
    Perfil, anio_actual,
)
from academico.rut import calcular_dv

NOMBRES = ["Sofía", "Benjamín", "Isidora", "Agustín", "Florencia", "Vicente", "Emilia", "Matías", "Antonella",
           "Tomás", "Josefa", "Maximiliano", "Martina", "Joaquín", "Catalina", "Lucas", "Trinidad", "Cristóbal"]
CALLES = ["Av. Libertad", "Calle Arauco", "Av. Collín", "Calle Maipón", "Av. O'Higgins", "Calle Itata",
          "Pasaje Los Aromos", "Calle 18 de Septiembre", "Av. Brasil", "Calle Constitución"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores"]


class Command(BaseCommand):
    help = "Carga datos de demostración (no usar en producción con datos reales)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(42)
        anio = anio_actual()
        datos_escuela = {"nombre": "Escuela Gabriela Mistral", "rbd": "3660", "comuna": "Chillán",
                         "director": "Ana Valenzuela Rojas", "jefe_utp": "Pedro Castillo Mena"}
        escuela = Establecimiento.objects.first()
        if escuela is None:
            Establecimiento.objects.create(**datos_escuela)
        else:
            for campo, valor in datos_escuela.items():
                setattr(escuela, campo, valor)
            escuela.save()

        def usuario(username, nombre, apellido, rol):
            u, creado = User.objects.get_or_create(username=username, defaults={"first_name": nombre, "last_name": apellido})
            if creado:
                u.set_password("demo1234")
                u.save()
            Perfil.objects.update_or_create(usuario=u, defaults={"rol": rol})
            return u

        usuario("sostenedor", "Ricardo", "Ibáñez Cortés", Perfil.Rol.SOSTENEDOR)
        usuario("director", "Ana", "Valenzuela Rojas", Perfil.Rol.DIRECTOR)
        usuario("inspector", "Mónica", "Saavedra Lillo", Perfil.Rol.INSPECTOR)
        usuario("convivencia", "Felipe", "Bravo Olave", Perfil.Rol.CONVIVENCIA)
        hist = usuario("profe.historia", "Claudia", "Fuentes Vidal", Perfil.Rol.PROFESOR)
        usuario("utp", "Pedro", "Castillo Mena", Perfil.Rol.UTP)
        mate = usuario("profe.matematica", "Carla", "Núñez Pino", Perfil.Rol.PROFESOR)
        leng = usuario("profe.lenguaje", "Jorge", "Reyes Lagos", Perfil.Rol.PROFESOR)
        cien = usuario("profe.ciencias", "Daniela", "Vergara Toro", Perfil.Rol.PROFESOR)

        fichas = [
            # usuario, rut, cargo, título, mención, contrato, horas, primer ciclo
            ("director", 12_345_670, "DIRECTIVO", "Profesora de Educación General Básica", "Gestión educacional", "TITULAR", 44, False),
            ("utp", 13_456_780, "TECNICO", "Profesor de Educación General Básica", "Currículum y evaluación", "TITULAR", 44, False),
            ("inspector", 14_567_890, "DIRECTIVO", "Profesora de Historia y Geografía", "", "TITULAR", 44, False),
            ("convivencia", 15_678_900, "ASISTENTE", "Psicólogo", "Convivencia escolar", "CONTRATA", 44, False),
            ("profe.matematica", 16_789_010, "DOCENTE", "Profesora de Educación General Básica", "Matemática", "TITULAR", 44, True),
            ("profe.lenguaje", 17_890_120, "DOCENTE", "Profesor de Educación General Básica", "Lenguaje y Comunicación", "CONTRATA", 38, True),
            ("profe.ciencias", 18_901_230, "DOCENTE", "Profesora de Biología y Ciencias Naturales", "", "TITULAR", 40, False),
            ("profe.historia", 19_012_340, "DOCENTE", "Profesora de Historia, Geografía y Ciencias Sociales", "", "CONTRATA", 30, False),
        ]
        for username, cuerpo, cargo, titulo, mencion, contrato, horas, ciclo in fichas:
            u = User.objects.get(username=username)
            if not Funcionario.objects.filter(usuario=u).exists():
                Funcionario.objects.get_or_create(rut=f"{cuerpo}-{calcular_dv(cuerpo)}", defaults={
                    "usuario": u, "nombres": u.first_name, "apellido_paterno": u.last_name.split()[0],
                    "apellido_materno": " ".join(u.last_name.split()[1:]), "cargo": cargo, "titulo": titulo,
                    "mencion": mencion, "tipo_contrato": contrato, "horas_contrato": horas, "primer_ciclo": ciclo,
                    "email": f"{username}@ejemplo.cl"})

        asignaturas = {}
        for i, nombre in enumerate(["Lenguaje y Comunicación", "Matemática", "Ciencias Naturales",
                                    "Historia, Geografía y Cs. Sociales", "Inglés", "Educación Física y Salud"]):
            asignaturas[nombre], _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={"orden": i})
        profes = {"Matemática": mate, "Lenguaje y Comunicación": leng, "Ciencias Naturales": cien,
                  "Historia, Geografía y Cs. Sociales": hist, "Inglés": hist}

        jefes = [mate, leng, cien]
        niveles = ["1° Básico", "2° Básico", "3° Básico", "4° Básico", "5° Básico", "6° Básico", "7° Básico", "8° Básico"]
        for orden, nombre_nivel in enumerate(niveles, start=1):
            nivel, _ = Nivel.objects.get_or_create(nombre=nombre_nivel, defaults={"orden": orden})
            if nivel.orden != orden:
                nivel.orden = orden
                nivel.save(update_fields=["orden"])
            for letra in "AB":
                jefe = jefes[(orden * 2 + ord(letra)) % 3]
                curso, _ = Curso.objects.get_or_create(nivel=nivel, letra=letra, anio=anio,
                                                       defaults={"profesor_jefe": jefe})
                acs = []
                for nombre_asig, asig in asignaturas.items():
                    ac, _ = AsignaturaCurso.objects.get_or_create(curso=curso, asignatura=asig,
                                                                  defaults={"profesor": profes.get(nombre_asig)})
                    acs.append(ac)
                if Evaluacion.objects.filter(asignatura_curso__curso=curso).exists():
                    continue  # curso ya poblado: el arranque queda rápido
                ests = []
                rut_base = 21_000_000 + orden * 100_000 + (ord(letra) - ord("A")) * 50_000
                for _ in range(12):
                    rut_base += random.randint(1000, 3500)
                    est, _ = Estudiante.objects.get_or_create(rut=f"{rut_base}-{calcular_dv(rut_base)}", defaults={
                        "nombres": random.choice(NOMBRES), "apellido_paterno": random.choice(APELLIDOS),
                        "apellido_materno": random.choice(APELLIDOS), "curso": curso,
                        "fecha_nacimiento": date(anio - orden - 6, random.randint(1, 12), random.randint(1, 28)),
                        "direccion": f"{random.choice(CALLES)} {random.randint(100, 2500)}",
                        "comuna": random.choice(["Chillán", "Chillán", "Chillán Viejo"]),
                        "telefono": f"+56 9 {random.randint(1000, 9999)} {random.randint(1000, 9999)}",
                        "apoderado_nombre": f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}",
                        "apoderado_telefono": f"+56 9 {random.randint(1000, 9999)} {random.randint(1000, 9999)}",
                    })
                    ests.append(est)
                notas = []
                for ac in acs:
                    for sem in (1, 2):
                        for n in range(1, 4):
                            ev = Evaluacion.objects.create(asignatura_curso=ac, nombre=f"Prueba {n}", semestre=sem,
                                                           fecha=date(anio, 3 + n + (sem - 1) * 4, 15))
                            for est in ests:
                                nota = Decimal(str(round(min(7, max(1, random.gauss(5.4, 1.0))), 1)))
                                notas.append(Calificacion(evaluacion=ev, estudiante=est, nota=nota))
                Calificacion.objects.bulk_create(notas, ignore_conflicts=True)
                for est in random.sample(ests, 3):
                    tipo = random.choice([Anotacion.Tipo.POSITIVA, Anotacion.Tipo.NEGATIVA])
                    Anotacion.objects.create(
                        estudiante=est, tipo=tipo, gravedad="LEVE" if tipo == "NEGATIVA" else "",
                        descripcion=("Destaca por su participación en clases." if tipo == "POSITIVA"
                                     else "No trae materiales de trabajo."),
                        fecha=date(anio, 5, random.randint(1, 28)), autor=jefe)
        self.stdout.write(self.style.SUCCESS(
            "Datos de demostración listos. Usuarios: sostenedor, director, utp, inspector, convivencia, "
            "profe.historia, profe.matematica, profe.lenguaje, profe.ciencias (contraseña: demo1234)"))
