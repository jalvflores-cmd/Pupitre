"""Crea datos de demostración: usuarios, cursos, asignaturas, estudiantes, notas y anotaciones.

Uso: python manage.py datos_demo
Usuarios creados (contraseña: demo1234): sostenedor, director, utp, inspector, convivencia,
profe.historia (profesor de asignatura), profe.matematica, profe.lenguaje, profe.ciencias (además profesores jefe)
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academico.models import (
    Anotacion, Asignatura, AsignaturaCurso, AsistenciaClase, Calificacion, Clase, Curso, Establecimiento, Estudiante, Evaluacion, Funcionario,
    Nivel,
    Perfil, Religion, anio_actual, Entrevista, RedApoyo,
)
from academico.importacion import reordenar_niveles
from academico.tenencia import en_establecimiento
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
        from academico.curriculo import cargar_oficiales
        from academico.models import ObjetivoAprendizaje
        cargar_oficiales(ObjetivoAprendizaje)
        datos_escuela = {"nombre": "Escuela Gabriela Mistral", "rbd": "3660", "comuna": "Chillán", "region": "Ñuble",
                         "director": "Jorge Sandoval Morales", "jefe_utp": "Pedro Castillo Mena"}
        escuela = Establecimiento.objects.order_by("pk").first()
        if escuela is None:
            escuela = Establecimiento.objects.create(**datos_escuela)
        elif escuela.nombre in ("Colegio Demostración", "Establecimiento educacional"):  # solo reemplaza nombres provisorios, nunca datos editados
            for campo, valor in datos_escuela.items():
                setattr(escuela, campo, valor)
            escuela.save()
        elif not escuela.region:  # completa solo campos vacíos
            escuela.region = "Ñuble"
            escuela.save(update_fields=["region"])

        if escuela.oferta != Establecimiento.Oferta.BASICA and escuela.nombre == "Escuela Gabriela Mistral":
            escuela.oferta = Establecimiento.Oferta.BASICA
            escuela.save(update_fields=["oferta"])
        with en_establecimiento(escuela):
            self.demo_escuela(anio)
            self.demo_libro(anio, cursos=2)
            self.demo_alertas(anio)
            self.demo_resultados(escuela)
        self.demo_superadmin()
        for datos in LICEOS:
            self.demo_liceo(anio, datos)
            liceo = Establecimiento.objects.filter(nombre=datos["nombre"]).first()
            if liceo:
                with en_establecimiento(liceo):
                    self.demo_libro(anio, cursos=1)
                    self.demo_resultados(liceo)
        self.demo_red(escuela)
        self.demo_personal(escuela)
        self.demo_horarios(anio)
        self.demo_administrativo(anio)
        self.demo_calendario()
        self.stdout.write(self.style.SUCCESS(
            "Datos de demostración listos (contraseña de todos los usuarios: demo1234)."))

    def demo_escuela(self, anio):
        def usuario(username, nombre, apellido, rol):
            u, creado = User.objects.get_or_create(username=username, defaults={"first_name": nombre, "last_name": apellido})
            if creado:
                u.set_password("demo1234")
                u.save()
            Perfil.objects.get_or_create(usuario=u, defaults={"rol": rol})  # no pisa cambios hechos en el sitio
            return u

        usuario("sostenedor", "Ricardo", "Ibáñez Cortés", Perfil.Rol.SOSTENEDOR)
        usuario("director", "Jorge", "Sandoval Morales", Perfil.Rol.DIRECTOR)
        usuario("inspector", "Mónica", "Saavedra Lillo", Perfil.Rol.INSPECTOR)
        usuario("convivencia", "Felipe", "Bravo Olave", Perfil.Rol.CONVIVENCIA)
        hist = usuario("profe.historia", "Claudia", "Fuentes Vidal", Perfil.Rol.PROFESOR)
        usuario("utp", "Pedro", "Castillo Mena", Perfil.Rol.UTP)
        mate = usuario("profe.matematica", "Carla", "Núñez Pino", Perfil.Rol.PROFESOR)
        leng = usuario("profe.lenguaje", "Jorge", "Reyes Lagos", Perfil.Rol.PROFESOR)
        cien = usuario("profe.ciencias", "Daniela", "Vergara Toro", Perfil.Rol.PROFESOR)
        ingl = usuario("profe.ingles", "Valentina", "Ortiz Fuentealba", Perfil.Rol.PROFESOR)
        arte = usuario("profe.artes", "Sebastián", "Lagos Riquelme", Perfil.Rol.PROFESOR)
        edfi = usuario("profe.edfisica", "Rodrigo", "Muñoz Sanhueza", Perfil.Rol.PROFESOR)
        reli = usuario("profe.religion", "Patricia", "Cifuentes Jara", Perfil.Rol.PROFESOR)
        bas1 = usuario("profe.basica1", "Paula", "Tapia Bustos", Perfil.Rol.PROFESOR)
        bas2 = usuario("profe.basica2", "Marcelo", "Contreras Vega", Perfil.Rol.PROFESOR)

        fichas = [
            # usuario, rut, cargo, título, mención, contrato, horas, primer ciclo
            ("director", 12_345_670, "DIRECTIVO", "Profesor de Educación General Básica", "Gestión educacional", "TITULAR", 44, False),
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
                    "usuario": u, "nombres": u.first_name or u.username, "apellido_paterno": (u.last_name.split() or ["—"])[0],
                    "apellido_materno": " ".join(u.last_name.split()[1:]), "cargo": cargo, "titulo": titulo,
                    "mencion": mencion, "tipo_contrato": contrato, "horas_contrato": horas, "primer_ciclo": ciclo,
                    "email": f"{username}@ejemplo.cl"})

        asignaturas = {}
        for i, nombre in enumerate(["Lenguaje y Comunicación", "Matemática", "Ciencias Naturales",
                                    "Historia, Geografía y Cs. Sociales", "Inglés", "Educación Física y Salud"]):
            asignaturas[nombre], _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={"orden": i})
        profes = {"Matemática": mate, "Lenguaje y Comunicación": leng, "Ciencias Naturales": cien,
                  "Historia, Geografía y Cs. Sociales": hist, "Inglés": ingl}

        jefes = [mate, leng, cien]
        nuevos_jefes = [bas1, bas2, bas1, bas2, leng, mate, cien, ingl, arte, edfi, leng, mate, cien, ingl, arte, edfi]
        niveles = ["1° Básico", "2° Básico", "3° Básico", "4° Básico", "5° Básico", "6° Básico", "7° Básico", "8° Básico"]
        for orden, nombre_nivel in enumerate(niveles, start=1):
            nivel, _ = Nivel.objects.get_or_create(nombre=nombre_nivel, defaults={"orden": orden + 2})
            for letra in "AB":
                jefe = jefes[(orden * 2 + ord(letra)) % 3]
                jefe_nuevo = nuevos_jefes[(orden - 1) * 2 + (ord(letra) - ord("A"))]
                curso, _ = Curso.objects.get_or_create(nivel=nivel, letra=letra, anio=anio,
                                                       defaults={"profesor_jefe": jefe_nuevo})
                if curso.profesor_jefe_id == jefe.id and jefe.id != jefe_nuevo.id:
                    curso.profesor_jefe = jefe_nuevo  # solo cambia la asignación original de la demo
                    curso.save(update_fields=["profesor_jefe"])
                acs = []
                for nombre_asig, asig in asignaturas.items():
                    if nombre_asig == "Lenguaje y Comunicación" and orden >= 7 and AsignaturaCurso.objects.filter(
                            curso=curso, asignatura__nombre="Lengua y Literatura").exists():
                        continue
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
        # Solo estudiantes ficticios de la demo (RUT 21.xxx.xxx); nunca se inventa el credo de estudiantes reales
        for est in Estudiante.objects.filter(religion="", rut__regex=r"^21[0-9]{6}-[0-9K]$"):
            est.religion = random.choices([Religion.CATOLICA, Religion.EVANGELICA, Religion.NO_OPTA], [65, 25, 10])[0]
            est.save(update_fields=["religion"])
        self.completar_plan(anio, {"Lenguaje y Comunicación": leng, "Lengua y Literatura": leng, "Matemática": mate,
                                   "Ciencias Naturales": cien, "Tecnología": cien, "Historia, Geografía y Cs. Sociales": hist,
                                   "Inglés": ingl, "Artes Visuales": arte, "Música": arte, "Educación Física y Salud": edfi,
                                   "Religión Católica": reli, "Religión Evangélica": reli},
                            {"Taller de Deportes": edfi, "Taller de Robótica": cien, "Taller de Arte y Folclor": arte})
        reordenar_niveles()
        for nivel in Nivel.objects.filter(decreto_plan_estudios=""):
            if nivel.ensenanza == "BASICA":
                grado = nivel.orden - 2
                nivel.decreto_plan_estudios = ("Decreto Exento N° 2960 de 2012" if grado <= 6
                                               else "Decreto Exento N° 628 de 2016")
                nivel.save(update_fields=["decreto_plan_estudios"])
        femeninos = {"Sofía", "Isidora", "Florencia", "Emilia", "Antonella", "Josefa", "Martina", "Catalina", "Trinidad"}
        for est in Estudiante.objects.filter(genero="", porcentaje_asistencia=None):
            est.genero = "F" if est.nombres.split()[0] in femeninos else "M"
            est.porcentaje_asistencia = Decimal(str(round(random.uniform(78, 99), 1)))
            est.save(update_fields=["genero", "porcentaje_asistencia"])
        self.corregir_director()
        self.demo_convivencia(anio)


    def demo_convivencia(self, anio):
        """Ejemplos de derivación, protocolo, red externa y entrevista (solo con estudiantes ficticios, una vez)."""
        if Entrevista.objects.exists() or RedApoyo.objects.exists():
            return
        ficticios = list(Estudiante.objects.filter(rut__regex=r"^21[0-9]{6}-[0-9K]$", activo=True,
                                                   curso__anio=anio).select_related("curso").order_by("rut")[:40])
        if len(ficticios) < 3:
            return
        conv = User.objects.filter(username="convivencia").first()
        a, b, c = ficticios[5], ficticios[17], ficticios[29]
        grave = Anotacion.objects.create(
            estudiante=a, tipo=Anotacion.Tipo.NEGATIVA, gravedad="GRAVE", fecha=date(anio, 9, 8),
            descripcion="Durante el recreo empuja reiteradamente a un compañero y lo insulta frente al grupo.",
            medida="Se separa a los estudiantes y se informa a Inspectoría.", autor=a.curso.profesor_jefe,
            derivada=True, estado_derivacion="EN_PROCESO", protocolo="MALTRATO_ESTUDIANTES",
            seguimiento="Se activa protocolo de maltrato entre estudiantes. Entrevistas con ambos apoderados.")
        Anotacion.objects.create(
            estudiante=b, tipo=Anotacion.Tipo.NEGATIVA, gravedad="GRAVE", fecha=date(anio, 10, 14),
            descripcion="Se retira de la sala sin autorización y no regresa a la clase.", autor=b.curso.profesor_jefe,
            derivada=True, estado_derivacion="PENDIENTE")
        RedApoyo.objects.create(
            estudiante=c, institucion="MEJOR_NINEZ", programa="PPF Chillán (ejemplo)",
            profesional="Dupla psicosocial del programa", fecha_inicio=date(anio, 4, 1), registrada_por=conv,
            observaciones="Ejemplo de demostración: seguimiento mensual con la dupla del programa.")
        Entrevista.objects.create(
            estudiante=a, tipo=Entrevista.Tipo.PROTOCOLO, fecha=date(anio, 9, 9), anotacion=grave,
            protocolo="MALTRATO_ESTUDIANTES", entrevistado=a.apoderado_nombre, parentesco="Apoderado(a)",
            motivo="Informar la activación del protocolo por maltrato entre estudiantes ocurrido el 8 de septiembre.",
            desarrollo="Se informa al apoderado(a) de los hechos registrados. Indica que en el hogar no ha observado "
                       "cambios de conducta y se compromete a conversar con el estudiante.",
            acuerdos="Seguimiento quincenal con Convivencia Escolar.",
            compromisos_apoderado="Asistir a las citaciones y reforzar en el hogar el buen trato.",
            compromisos_estudiante="Respetar a sus compañeros y pedir ayuda a un adulto ante un conflicto.",
            compromisos_establecimiento="Acompañamiento de la dupla psicosocial y monitoreo en recreos.",
            fecha_seguimiento=date(anio, 9, 23), entrevistador=conv)

    def corregir_director(self):
        """El director actual de la escuela es Jorge Sandoval Morales: reemplaza el nombre antiguo de la demo."""
        Establecimiento.objects.filter(director__in=["Ana Valenzuela Rojas", ""]).update(director="Jorge Sandoval Morales")
        User.objects.filter(first_name="Ana", last_name="Valenzuela Rojas").update(
            first_name="Jorge", last_name="Sandoval Morales")
        for f in Funcionario.objects.filter(nombres="Ana", apellido_paterno="Valenzuela", apellido_materno="Rojas"):
            f.nombres, f.apellido_paterno, f.apellido_materno = "Jorge", "Sandoval", "Morales"
            if f.titulo == "Profesora de Educación General Básica":
                f.titulo = "Profesor de Educación General Básica"
            f.save()

    # Plan de estudios oficial de Enseñanza Básica (horas semanales referenciales con JEC)
    PLAN = {
        "1-4": [("Lenguaje y Comunicación", 8), ("Inglés", 2), ("Matemática", 6),
                ("Historia, Geografía y Cs. Sociales", 3), ("Ciencias Naturales", 3), ("Artes Visuales", 2),
                ("Música", 2), ("Educación Física y Salud", 4), ("Tecnología", 1), ("Orientación", 0.5), ("Religión Católica", 2), ("Religión Evangélica", 2)],
        "5-6": [("Lenguaje y Comunicación", 6), ("Inglés", 3), ("Matemática", 6),
                ("Historia, Geografía y Cs. Sociales", 4), ("Ciencias Naturales", 4), ("Artes Visuales", 1.5),
                ("Música", 1.5), ("Educación Física y Salud", 2), ("Tecnología", 1), ("Orientación", 1), ("Religión Católica", 2), ("Religión Evangélica", 2)],
        "7-8": [("Lengua y Literatura", 6), ("Inglés", 3), ("Matemática", 6),
                ("Historia, Geografía y Cs. Sociales", 4), ("Ciencias Naturales", 4), ("Artes Visuales", 1.5),
                ("Música", 1.5), ("Educación Física y Salud", 2), ("Tecnología", 1), ("Orientación", 1), ("Religión Católica", 2), ("Religión Evangélica", 2)],
    }
    ORDEN = ["Lenguaje y Comunicación", "Lengua y Literatura", "Inglés", "Matemática",
             "Historia, Geografía y Cs. Sociales", "Ciencias Naturales", "Artes Visuales", "Música",
             "Educación Física y Salud", "Tecnología", "Orientación", "Religión Católica", "Religión Evangélica"]

    def completar_plan(self, anio, profes, talleres):
        """Agrega las asignaturas del plan oficial y talleres JEC que falten (sin tocar lo existente)."""
        asignaturas = {}
        # Si ya existe Religión Evangélica, la actualización de talleres ya se hizo y no se vuelve a tocar
        self.talleres_revisados = Asignatura.objects.filter(nombre="Religión Evangélica").exists()
        orden_demo_antiguo = {"Lenguaje y Comunicación": 0, "Matemática": 1, "Ciencias Naturales": 2,
                              "Historia, Geografía y Cs. Sociales": 3, "Inglés": 4, "Educación Física y Salud": 5}
        # La antigua asignatura "Religión" pasa a ser Religión Católica (conserva sus notas)
        antigua_religion = Asignatura.objects.filter(nombre="Religión").first()
        if antigua_religion and not Asignatura.objects.filter(nombre="Religión Católica").exists():
            antigua_religion.nombre = "Religión Católica"
            antigua_religion.religion = Religion.CATOLICA
            antigua_religion.save(update_fields=["nombre", "religion"])
        credos = {"Religión Católica": Religion.CATOLICA, "Religión Evangélica": Religion.EVANGELICA}
        for i, nombre in enumerate(self.ORDEN):
            asig, _ = Asignatura.objects.get_or_create(nombre=nombre, defaults={
                "orden": i, "incide_en_promedio": nombre != "Orientación" and nombre not in credos,
                "con_concepto": nombre == "Orientación", "religion": credos.get(nombre, "")})
            if orden_demo_antiguo.get(nombre) == asig.orden and asig.orden != i:
                asig.orden = i
                asig.save(update_fields=["orden"])
            if nombre == "Orientación" and not self.talleres_revisados and not asig.con_concepto:
                asig.con_concepto = True  # se mantenía con concepto antes de esta actualización
                asig.save(update_fields=["con_concepto"])
            asignaturas[nombre] = asig
        for nombre in talleres:
            asignaturas[nombre], creado = Asignatura.objects.get_or_create(nombre=nombre, defaults={
                "orden": 90, "tipo": Asignatura.Tipo.TALLER, "incide_en_promedio": True})
            if not creado and not asignaturas[nombre].incide_en_promedio and not self.talleres_revisados:
                # Los talleres de la demo se crearon antes sin incidencia; ahora se califican con nota
                asignaturas[nombre].incide_en_promedio = True
                asignaturas[nombre].save(update_fields=["incide_en_promedio"])
        for curso in Curso.objects.filter(anio=anio, nivel__nombre__iregex=r"^[1-8]° básico$").select_related("nivel"):
            grado = int(curso.nivel.nombre[0])
            plan = self.PLAN["1-4" if grado <= 4 else "5-6" if grado <= 6 else "7-8"]
            if grado >= 7:  # en 7° y 8° la asignatura se llama Lengua y Literatura
                antigua = AsignaturaCurso.objects.filter(curso=curso, asignatura__nombre="Lenguaje y Comunicación").first()
                if antigua and not AsignaturaCurso.objects.filter(curso=curso, asignatura__nombre="Lengua y Literatura").exists():
                    antigua.asignatura = asignaturas["Lengua y Literatura"]
                    antigua.save(update_fields=["asignatura"])
                elif antigua and not antigua.evaluaciones.exists():
                    antigua.delete()  # duplicado vacío
            items = list(plan) + [(t, 2) for t in talleres
                                  if (t == "Taller de Deportes" and grado <= 4) or (t == "Taller de Robótica" and grado >= 5)
                                  or t == "Taller de Arte y Folclor"]
            for nombre, horas in items:
                profesor = profes.get(nombre) or talleres.get(nombre) or curso.profesor_jefe
                ac, creado = AsignaturaCurso.objects.get_or_create(curso=curso, asignatura=asignaturas[nombre], defaults={
                    "profesor": profesor, "horas_semanales": horas})
                if not creado and ac.horas_semanales is None:
                    ac.horas_semanales = horas
                    ac.save(update_fields=["horas_semanales"])
                if creado:
                    self.poblar_notas(ac, anio)

    def poblar_notas(self, ac, anio):
        estudiantes = [e for e in ac.curso.estudiantes.filter(activo=True) if e.cursa(ac.asignatura)]
        if not estudiantes:
            return
        notas = []
        for sem in (1, 2):
            for n in range(1, 3):
                ev = Evaluacion.objects.create(asignatura_curso=ac, nombre=f"Evaluación {n}", semestre=sem,
                                               fecha=date(anio, 4 + n + (sem - 1) * 4, 20))
                for est in estudiantes:
                    nota = Decimal(str(round(min(7, max(2, random.gauss(5.7, 0.8))), 1)))
                    notas.append(Calificacion(evaluacion=ev, estudiante=est, nota=nota))
        Calificacion.objects.bulk_create(notas, ignore_conflicts=True)

    def demo_resultados(self, est):
        """SIMCE y PAES ficticios (solo si el establecimiento no tiene resultados registrados)."""
        from academico.models import ResultadoPaes, ResultadoSimce

        if ResultadoSimce.objects.exists() or ResultadoPaes.objects.exists():
            return
        rnd = random.Random(f"resultados-{est.nombre}")
        basica = est.oferta == Establecimiento.Oferta.BASICA
        niveles = {"4B": (262, 260), "8B": (243, 255)} if basica else {"2M": (250, 252)}
        tp = est.oferta == Establecimiento.Oferta.TP
        for nivel, (lec_nac, mat_nac) in niveles.items():
            for prueba, nac in (("LEC", lec_nac), ("MAT", mat_nac)):
                base = nac + rnd.randint(-25, 10) - (12 if tp else 0)
                for anio in (2018, 2019, 2022, 2023, 2024):
                    base += rnd.randint(-8, 10)
                    ResultadoSimce.objects.create(
                        anio=anio, nivel=nivel, prueba=prueba, puntaje=base, puntaje_nacional=nac + rnd.randint(-4, 4),
                        puntaje_gse=nac - 12 + rnd.randint(-5, 5), evaluados=rnd.randint(25, 70),
                        pct_adecuado=Decimal(str(round(rnd.uniform(15, 40), 1))),
                        pct_insuficiente=Decimal(str(round(rnd.uniform(25, 50), 1))))
        if not basica:
            for prueba, nac in (("CL", 560), ("M1", 545), ("M2", 520), ("HI", 550)):
                base = nac - rnd.randint(40, 90) - (40 if tp else 0)
                for anio in (2023, 2024, 2025, 2026):
                    base += rnd.randint(-10, 15)
                    ResultadoPaes.objects.create(anio=anio, prueba=prueba, puntaje=base,
                                                 puntaje_nacional=nac + rnd.randint(-6, 6),
                                                 rindieron=rnd.randint(8, 30) if prueba in ("M2", "HI") else rnd.randint(30, 60))

    def demo_alertas(self, anio):
        """Para que la demo muestre alertas de bajo rendimiento: solo si no hay ninguna nota roja."""
        from academico.alertas import bajo_rendimiento

        cursos = list(Curso.objects.filter(anio=anio).order_by("-nivel__orden", "letra")[:3])
        if bajo_rendimiento(cursos):
            return
        rnd = random.Random(f"alertas-{anio}")
        for curso in cursos:
            ests = list(curso.estudiantes.filter(activo=True))
            if not ests:
                continue
            est = rnd.choice(ests)
            acs = [ac for ac in curso.asignaturas_curso.select_related("asignatura")
                   if ac.asignatura.incide_en_promedio and est.cursa(ac.asignatura)][:2 if curso == cursos[0] else 1]
            for ac in acs:
                for c in Calificacion.objects.filter(estudiante=est, evaluacion__asignatura_curso=ac):
                    c.nota = Decimal(str(round(rnd.uniform(2.5, 3.7), 1)))
                    c.save(update_fields=["nota"])

    # ------------------------------------------------------------------ Libro de clases
    def demo_libro(self, anio, cursos=1):
        """Leccionario y asistencia de las últimas semanas (solo si el establecimiento aún no tiene clases)."""
        from academico.libro import recalcular_asistencia, semestre_de

        hoy = date.today()
        if Clase.objects.exists() or hoy.year != anio:
            return
        rnd = random.Random(f"libro-{anio}")
        dias = []
        d = hoy - timedelta(days=21)
        while d <= hoy + timedelta(days=7):
            if d.weekday() < 5:
                dias.append(d)
            d += timedelta(days=1)
        lista = (Curso.objects.filter(anio=anio, profesor_jefe__isnull=False)
                 .order_by("-nivel__orden", "letra")[:cursos])
        from academico.curriculo import oas_para

        for curso in lista:
            acs = list(curso.asignaturas_curso.filter(profesor__isnull=False).select_related("asignatura", "profesor"))
            oas_de = {ac.pk: list(oas_para(ac)) for ac in acs}
            estudiantes = list(curso.estudiantes.filter(activo=True))
            faltador = {e.id: rnd.choice([0.02, 0.03, 0.04, 0.06]) for e in estudiantes}
            for d in dias:
                del_dia = [ac for i, ac in enumerate(acs)
                           if d.weekday() in ({i % 5, (i + 2) % 5} if (ac.horas_semanales or 0) >= 4 else {i % 5})]
                ausentes_hoy = {e.id for e in estudiantes if rnd.random() < faltador[e.id]}
                for slot, ac in enumerate(del_dia[:5]):
                    n = Clase.objects.filter(asignatura_curso=ac).count()
                    oa, actividad = _contenido_demo(ac.asignatura.nombre, n)
                    oficiales = oas_de[ac.pk]
                    oficial = oficiales[(n // 2) % len(oficiales)] if oficiales else None
                    if oficial:
                        oa = f"OA {oficial.numero}: {oficial.texto}"
                    clase = Clase.objects.create(
                        asignatura_curso=ac, fecha=d, hora_inicio=HORARIO[slot],
                        bloques=2, unidad=f"Unidad {3 if semestre_de(d) == 2 else 1}", objetivo=oa,
                        actividades=actividad, recursos="Texto escolar, guía de trabajo, proyector", creada_por=ac.profesor)
                    if oficial:
                        clase.oas.add(oficial)
                    if d > hoy:
                        if n == 6:
                            ev = Evaluacion.objects.create(asignatura_curso=ac, nombre="Prueba de unidad", fecha=d,
                                                           semestre=semestre_de(d))
                            clase.evaluacion = ev
                            clase.save(update_fields=["evaluacion"])
                        continue
                    cursan = [e for e in estudiantes if e.cursa(ac.asignatura)]
                    registros = []
                    for e in cursan:
                        estado = "A" if e.id in ausentes_hoy else ("T" if slot == 0 and rnd.random() < 0.03 else "P")
                        registros.append(AsistenciaClase(clase=clase, estudiante=e, estado=estado))
                    AsistenciaClase.objects.bulk_create(registros)
                    clase.asistencia_registrada = True
                    if d < hoy - timedelta(days=2):
                        clase.firmada_por = ac.profesor
                        clase.firmada_en = timezone.make_aware(datetime.combine(d, clase.hora_inicio)) + timedelta(hours=1, minutes=25)
                    clase.save()
            recalcular_asistencia(curso)

    # ------------------------------------------------------------------ Plataforma con varios establecimientos

    def demo_red(self, escuela):
        """Niveles: un sostenedor ficticio con la escuela y los tres liceos (su personal queda como personal del
        sostenedor). Solo crea lo que falta y solo asigna establecimientos que aún no tienen sostenedor."""
        from academico.models import Sostenedor

        def usuario(username, nombre, apellido, **perfil):
            u, creado = User.objects.get_or_create(username=username, defaults={"first_name": nombre,
                                                                                "last_name": apellido})
            if creado:
                u.set_password("demo1234")
                u.save()
            Perfil.objects.get_or_create(usuario=u, defaults=perfil)

        sost, _ = Sostenedor.objects.get_or_create(nombre="Corporación Educacional Ñuble (demo)",
                                                   defaults={"rut": "65.123.456-7"})
        nombres = [d["nombre"] for d in LICEOS] + ["Escuela Gabriela Mistral"]
        Establecimiento.objects.filter(nombre__in=nombres, sostenedor__isnull=True).update(sostenedor=sost)
        usuario("admin.red", "Carolina", "Fuentes Lagos", rol=Perfil.Rol.ADMIN_SOSTENEDOR, sostenedor=sost)
        usuario("sostenedor.red", "Hernán", "Muñoz Parra", rol=Perfil.Rol.SOSTENEDOR, sostenedor=sost)
        usuario("admin.escuela", "Marcela", "Riquelme Soto", rol=Perfil.Rol.ADMIN, establecimiento=escuela)

    def demo_personal(self, escuela):
        """Tramos, evaluación docente, % de prioritarios y montos ilustrativos. Solo completa lo que está vacío."""
        from academico.models import ParametrosPersonal, Sostenedor

        escuela.refresh_from_db()
        rnd = random.Random(7)
        ests = [escuela] + list(Establecimiento.objects.filter(nombre__in=[d["nombre"] for d in LICEOS]))
        for est, pct, rural in zip(ests, (82, 64, 71, 58), (False, False, False, True)):
            if est.pct_prioritarios is None:
                est.pct_prioritarios, est.rural = pct, rural
                est.save(update_fields=["pct_prioritarios", "rural"])
            with en_establecimiento(est):
                if not Funcionario.objects.exists():  # liceos demo: fichas a partir de sus usuarios
                    for i, perfil in enumerate(Perfil.objects.filter(establecimiento=est).select_related("usuario")):
                        u = perfil.usuario
                        cargo = {"DIRECTOR": "DIRECTIVO", "UTP": "TECNICO"}.get(perfil.rol, "DOCENTE")
                        cuerpo = 20_000_000 + est.pk * 1000 + i
                        Funcionario.objects.create(
                            usuario=u, rut=f"{cuerpo}-{calcular_dv(cuerpo)}", nombres=u.first_name or u.username,
                            apellido_paterno=(u.last_name.split() or ["—"])[0],
                            apellido_materno=" ".join(u.last_name.split()[1:]), cargo=cargo,
                            titulo="Profesor(a) de Educación Media", horas_contrato=rnd.choice([30, 38, 44, 44]))
                # profesores con clases y sin ficha: se agrega su ficha (para el análisis de dotación)
                con_ficha = set(Funcionario.objects.exclude(usuario=None).values_list("usuario_id", flat=True))
                for u in User.objects.filter(asignaturas_curso__curso__establecimiento=est).exclude(
                        pk__in=con_ficha).distinct():
                    cuerpo = 21_000_000 + est.pk * 1000 + u.pk
                    if not Funcionario.objects.filter(rut=f"{cuerpo}-{calcular_dv(cuerpo)}").exists():
                        Funcionario.objects.create(
                            usuario=u, rut=f"{cuerpo}-{calcular_dv(cuerpo)}", nombres=u.first_name or u.username,
                            apellido_paterno=(u.last_name.split() or ["—"])[0],
                            apellido_materno=" ".join(u.last_name.split()[1:]), cargo="DOCENTE",
                            titulo="Profesor(a)", horas_contrato=rnd.choice([30, 38, 44]))
                if not Funcionario.objects.exclude(tramo="").exists():
                    for f in Funcionario.objects.exclude(cargo=Funcionario.Cargo.ASISTENTE):
                        f.anios_experiencia = rnd.randint(1, 32)
                        f.tramo = ("INICIAL" if f.anios_experiencia < 4 else rnd.choice(
                            ["TEMPRANO", "AVANZADO", "AVANZADO", "EXPERTO_I", "EXPERTO_II"]))
                        f.evaluacion_docente = rnd.choice(["DESTACADO", "COMPETENTE", "COMPETENTE", "COMPETENTE",
                                                           "BASICO", "INSATISFACTORIO", ""])
                        f.evaluacion_anio = rnd.choice([2022, 2023, 2024, 2025]) if f.evaluacion_docente else None
                        f.brp_mencion = bool(f.mencion) or rnd.random() < 0.3
                        f.save()
        montos = {"brp_titulo": 95000, "brp_mencion": 32000, "por_bienio": 25000, "tramo_inicial": 30000,
                  "tramo_temprano": 90000, "tramo_avanzado": 210000, "tramo_experto_i": 380000,
                  "tramo_experto_ii": 560000}  # ilustrativos, solo para la demostración
        sost = Sostenedor.objects.filter(nombre="Corporación Educacional Ñuble (demo)").first()
        if sost and not ParametrosPersonal.objects.filter(sostenedor=sost).exists():
            ParametrosPersonal.objects.create(sostenedor=sost, **montos)
        if escuela.sostenedor_id is None and not ParametrosPersonal.objects.filter(establecimiento=escuela).exists():
            ParametrosPersonal.objects.create(establecimiento=escuela, **montos)

    def demo_horarios(self, anio):
        """Genera los horarios de cada establecimiento que aún no tiene ninguno."""
        from academico.horarios import generar
        from academico.models import HorarioClase

        for est in Establecimiento.objects.all():
            with en_establecimiento(est):
                cursos = Curso.objects.filter(anio=anio)
                if cursos.exists() and not HorarioClase.objects.exists():
                    generar(cursos, semilla=1)

    def demo_administrativo(self, anio):
        """Asistencia del personal de las últimas semanas y un PME con acciones y gastos SEP (solo si no hay)."""
        from academico.models import AccionPME, AsistenciaFuncionario, GastoSEP, PlanMejoramiento

        rnd = random.Random(11)
        hoy = timezone.localdate()
        dias = [hoy - timedelta(days=i) for i in range(1, 30) if (hoy - timedelta(days=i)).weekday() < 5]
        acciones_demo = [
            ("PEDAGOGICA", "Acompañamiento al aula con retroalimentación", "Jefe(a) de UTP", 3, 11, 1_800_000, "PROCESO", 60),
            ("PEDAGOGICA", "Reforzamiento de lectura y matemática en 1° y 2° ciclo", "Coordinación PIE", 4, 11, 6_500_000, "PROCESO", 55),
            ("PEDAGOGICA", "Compra de textos y material concreto", "Jefe(a) de UTP", 3, 5, 4_200_000, "EJECUTADA", 100),
            ("LIDERAZGO", "Jornadas de análisis de resultados con el consejo de profesores", "Director(a)", 3, 12, 600_000, "PROCESO", 50),
            ("CONVIVENCIA", "Talleres de convivencia y habilidades socioemocionales", "Encargado(a) de convivencia", 4, 10, 2_400_000, "PROCESO", 70),
            ("CONVIVENCIA", "Salidas pedagógicas y actividades de formación ciudadana", "Inspector(a) general", 5, 9, 3_000_000, "NO", 0),
            ("RECURSOS", "Renovación de equipamiento tecnológico de aula", "Director(a)", 4, 8, 7_500_000, "PROCESO", 40),
            ("RECURSOS", "Capacitación docente en evaluación formativa", "Jefe(a) de UTP", 6, 10, 2_000_000, "NO", 0),
        ]
        for est in Establecimiento.objects.all():
            with en_establecimiento(est):
                funcionarios = list(Funcionario.objects.filter(activo=True))
                if funcionarios and not AsistenciaFuncionario.objects.exists():
                    registros = []
                    for d in dias:
                        for f in funcionarios:
                            r = rnd.random()
                            estado = "P" if r < 0.86 else "T" if r < 0.93 else "A" if r < 0.96 else "L" if r < 0.985 else "PA"
                            registros.append(AsistenciaFuncionario(
                                funcionario=f, fecha=d, estado=estado,
                                entrada=time(8, rnd.randint(16, 40)) if estado == "T" else time(7, rnd.randint(40, 59)) if estado == "P" else None,
                                salida=time(17, rnd.randint(0, 20)) if estado in ("P", "T") else None,
                                minutos_atraso=rnd.randint(5, 25) if estado == "T" else 0))
                    AsistenciaFuncionario.objects.bulk_create(registros)
                if not PlanMejoramiento.objects.exists():
                    plan = PlanMejoramiento.objects.create(
                        anio=anio, presupuesto_sep=rnd.choice([38_000_000, 45_000_000, 52_000_000]), saldo_anterior=4_500_000,
                        objetivo_general="Mejorar los aprendizajes en lectura y matemática con foco en la evaluación formativa.")
                    for dim, nombre, resp, m1, m2, monto, estado, avance in acciones_demo:
                        a = AccionPME.objects.create(plan=plan, dimension=dim, nombre=nombre, responsable=resp,
                                                     inicio=date(anio, m1, 1), termino=date(anio, m2, 28), monto_sep=monto,
                                                     estado=estado, avance=avance,
                                                     medios_verificacion="Actas, listas de asistencia y registro fotográfico.")
                        for i in range(int(monto * avance / 100 // 900_000)):
                            GastoSEP.objects.create(plan=plan, accion=a, fecha=date(anio, min(m1 + i, 11), 10 + i),
                                                    categoria=rnd.choice(["RECURSOS", "EQUIPAMIENTO", "CAPACITACION", "PERSONAL"]),
                                                    detalle=f"{nombre[:60]} – compra {i + 1}", proveedor="Proveedor demo SpA",
                                                    documento=f"Factura {1000 + rnd.randint(1, 8999)}", monto=900_000)

    def demo_calendario(self):
        """Eventos del calendario alrededor de hoy (solo en establecimientos que aún no tienen ninguno)."""
        from academico.models import EventoCalendario

        hoy = timezone.localdate()

        def habil(dias):
            d = hoy + timedelta(days=dias)
            while d.weekday() >= 5:
                d += timedelta(days=1 if dias >= 0 else -1)
            return d

        gestion = ["DIRECTOR", "UTP", "INSPECTOR", "CONVIVENCIA"]
        eventos = [
            (0, time(15, 30), "Consejo de profesores", "CONSEJO", [], "Tabla: cierre del semestre, casos de asistencia y actividades de fin de año."),
            (1, None, "Entrega de planificaciones a UTP", "PLAZO", ["PROFESOR", "UTP"], "Planificaciones de la próxima unidad en el libro de clases."),
            (3, time(19, 0), "Reunión de apoderados", "APODERADOS", [], "Entrega de informes de notas parciales."),
            (6, time(11, 0), "Acto de fin de año", "ACTIVIDAD", [], ""),
            (8, None, "Plazo de cierre de notas del semestre", "PLAZO", ["PROFESOR", "UTP", "DIRECTOR"], ""),
            (-3, time(9, 0), "Reunión del equipo directivo", "REUNION", gestion, "Seguimiento del PME."),
        ]
        for est in Establecimiento.objects.all():
            with en_establecimiento(est):
                if EventoCalendario.objects.exists():
                    continue
                autor = User.objects.filter(perfil__establecimiento=est, perfil__rol="DIRECTOR").first()
                for dias, hora, titulo, tipo, roles, detalle in eventos:
                    EventoCalendario.objects.create(titulo=titulo, tipo=tipo, fecha=habil(dias), hora=hora, roles=roles,
                                                    descripcion=detalle, creado_por=autor)

    def demo_superadmin(self):
        u, creado = User.objects.get_or_create(username="superadmin", defaults={
            "first_name": "Administración", "last_name": "Plataforma Pupitre"})
        if creado:
            u.set_password("demo1234")
            u.save()
        Perfil.objects.get_or_create(usuario=u, defaults={"rol": Perfil.Rol.SUPERADMIN, "establecimiento": None})

    def demo_liceo(self, anio, datos):
        """Crea un liceo ficticio de Enseñanza Media (solo si no existe: nunca modifica uno existente)."""
        from academico.plan_oficial import aplicar_plan_media, decreto_media

        if Establecimiento.objects.filter(nombre=datos["nombre"]).exists():
            return
        rnd = random.Random(datos["sufijo"])
        est = Establecimiento.objects.create(
            nombre=datos["nombre"], oferta=datos["oferta"], comuna="Chillán", region="Ñuble",
            director=" ".join(datos["director"][:2]), jefe_utp=" ".join(datos["utp"][:2]),
            color_principal=datos["color"], pie_documentos=datos["lema"])
        with en_establecimiento(est):
            def usuario(username, nombre, apellido, rol):
                u, creado = User.objects.get_or_create(username=username, defaults={
                    "first_name": nombre, "last_name": apellido})
                if creado:
                    u.set_password("demo1234")
                    u.save()
                Perfil.objects.get_or_create(usuario=u, defaults={"rol": rol, "establecimiento": est})
                return u

            sx = datos["sufijo"]
            usuario(f"director.{sx}", *datos["director"], Perfil.Rol.DIRECTOR)
            usuario(f"utp.{sx}", *datos["utp"], Perfil.Rol.UTP)
            profes = [usuario(f"profe.{sx}" if i == 0 else f"profe{i + 1}.{sx}", n, a, Perfil.Rol.PROFESOR)
                      for i, (n, a) in enumerate(datos["profesores"])]
            niveles = {}
            for g, romano in enumerate(["I", "II", "III", "IV"], start=1):
                niveles[g], _ = Nivel.objects.get_or_create(nombre=f"{romano} Medio", defaults={
                    "orden": g + 10, "ensenanza": Nivel.Ensenanza.MEDIA})
            rut_base = 22_000_000 + datos["rut_base"]
            for c, (grado, letra, modalidad, especialidad, electivos) in enumerate(datos["cursos"]):
                curso = Curso.objects.create(nivel=niveles[grado], letra=letra, anio=anio, modalidad=modalidad,
                                             especialidad=especialidad, profesor_jefe=profes[c % len(profes)])
                curso.decreto_plan_estudios = decreto_media(curso)
                curso.save(update_fields=["decreto_plan_estudios"])
                aplicar_plan_media(curso, electivos)
                for i, ac in enumerate(curso.asignaturas_curso.select_related("asignatura")):
                    ac.profesor = profes[(i + c) % len(profes)]
                    ac.save(update_fields=["profesor"])
                ests = []
                for n in range(10):
                    rut_base += rnd.randint(1000, 3500)
                    nombre = rnd.choice(NOMBRES)
                    ests.append(Estudiante.objects.create(
                        rut=f"{rut_base}-{calcular_dv(rut_base)}", nombres=nombre,
                        apellido_paterno=rnd.choice(APELLIDOS), apellido_materno=rnd.choice(APELLIDOS), curso=curso,
                        fecha_nacimiento=date(anio - grado - 14, rnd.randint(1, 12), rnd.randint(1, 28)),
                        genero="F" if nombre in FEMENINOS else "M",
                        direccion=f"{rnd.choice(CALLES)} {rnd.randint(100, 2500)}", comuna="Chillán",
                        apoderado_nombre=f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)}",
                        apoderado_telefono=f"+56 9 {rnd.randint(1000, 9999)} {rnd.randint(1000, 9999)}",
                        religion=rnd.choices([Religion.CATOLICA, Religion.EVANGELICA, Religion.NO_OPTA], [60, 25, 15])[0],
                        porcentaje_asistencia=Decimal(str(round(rnd.uniform(80, 99), 1)))))
                notas = []
                for ac in curso.asignaturas_curso.select_related("asignatura"):
                    cursan = [e for e in ests if e.cursa(ac.asignatura)]
                    for sem in (1, 2):
                        for k in (1, 2):
                            ev = Evaluacion.objects.create(asignatura_curso=ac, nombre=f"Evaluación {k}", semestre=sem,
                                                           fecha=date(anio, 3 + k + (sem - 1) * 5, 15))
                            notas += [Calificacion(evaluacion=ev, estudiante=e, nota=Decimal(str(round(
                                min(7, max(2, rnd.gauss(5.4, 0.9))), 1)))) for e in cursan]
                Calificacion.objects.bulk_create(notas)
                for e in rnd.sample(ests, 2):
                    tipo = rnd.choice([Anotacion.Tipo.POSITIVA, Anotacion.Tipo.NEGATIVA])
                    Anotacion.objects.create(
                        estudiante=e, tipo=tipo, gravedad="LEVE" if tipo == "NEGATIVA" else "",
                        descripcion=("Destaca por su compromiso en el trabajo práctico." if tipo == "POSITIVA"
                                     else "Llega atrasado(a) reiteradamente a clases."),
                        fecha=date(anio, 6, rnd.randint(1, 28)), autor=curso.profesor_jefe)
        reordenar_niveles()


HORARIO = [time(8, 0), time(9, 45), time(11, 30), time(14, 0), time(15, 30)]

CONTENIDOS_DEMO = {
    "lengua": ("OA 3: Leer y familiarizarse con un amplio repertorio de literatura para aumentar su conocimiento del mundo.",
                 "Inicio: activación de conocimientos previos sobre el género narrativo.\nDesarrollo: lectura compartida y "
                 "preguntas de comprensión en parejas.\nCierre: ticket de salida con la idea principal del texto."),
    "matem": ("OA 6: Resolver problemas que involucren las cuatro operaciones con números naturales y fracciones.",
              "Inicio: problema desafío en la pizarra.\nDesarrollo: trabajo guiado con material concreto y ejercicios "
              "de la guía.\nCierre: puesta en común de estrategias de resolución."),
    "historia": ("OA 2: Explicar los principales procesos históricos y su impacto en la sociedad chilena actual.",
                 "Inicio: análisis de una fuente iconográfica.\nDesarrollo: lectura de fuentes primarias y línea de tiempo "
                 "grupal.\nCierre: síntesis colectiva de causas y consecuencias."),
    "ciencias": ("OA 4: Investigar experimentalmente y explicar fenómenos naturales usando el método científico.",
                 "Inicio: pregunta de investigación.\nDesarrollo: experimento en grupos y registro de observaciones.\n"
                 "Cierre: elaboración de conclusiones y comunicación de resultados."),
    "inglés": ("OA 5: Comprender textos orales y escritos breves en inglés sobre temas conocidos.",
               "Warm up: vocabulary game.\nDesarrollo: listening y actividad de comprensión.\nCierre: role play en parejas."),
    "física": ("OA 1: Aplicar habilidades motrices básicas y específicas en diferentes juegos y deportes.",
               "Inicio: calentamiento y movilidad articular.\nDesarrollo: circuito de habilidades y juego colectivo.\n"
               "Cierre: vuelta a la calma e hidratación."),
}


def _contenido_demo(asignatura, n):
    nombre = asignatura.lower()
    for clave, (oa, act) in CONTENIDOS_DEMO.items():
        if clave in nombre:
            return oa, act
    return (f"Desarrollar los objetivos de aprendizaje de {asignatura} correspondientes a la unidad en curso (clase {n + 1}).",
            "Inicio: presentación del objetivo de la clase.\nDesarrollo: actividad práctica individual y grupal.\n"
            "Cierre: retroalimentación y síntesis de lo aprendido.")


FEMENINOS = {"Sofía", "Isidora", "Florencia", "Emilia", "Antonella", "Josefa", "Martina", "Catalina", "Trinidad"}

# Liceos ficticios de demostración (nombres inventados, sin RBD real)
LICEOS = [
    {"nombre": "Liceo Los Coigües", "sufijo": "hc", "oferta": "HC", "color": "#1F5F4A", "rut_base": 100_000,
     "lema": "Liceo Científico-Humanista · Datos ficticios de demostración",
     "director": ("Marcela", "Riquelme Soto"), "utp": ("Andrés", "Vergara Lagos"),
     "profesores": [("Paulina", "Cárdenas Ruiz"), ("Rodrigo", "Saavedra Pino"), ("Camila", "Ortega Vidal"),
                    ("Felipe", "Navarro Bravo"), ("Javiera", "Gutiérrez Mena")],
     "cursos": [(1, "A", "", "", None), (2, "A", "", "", None),
                (3, "A", "HC", "", ["Biología de los Ecosistemas", "Física", "Límites, Derivadas e Integrales"]),
                (3, "B", "HC", "", ["Comprensión Histórica del Presente", "Taller de Literatura",
                                    "Lectura y Escritura Especializadas"]),
                (4, "A", "HC", "", ["Biología de los Ecosistemas", "Física", "Límites, Derivadas e Integrales"]),
                (4, "B", "HC", "", ["Comprensión Histórica del Presente", "Taller de Literatura",
                                    "Lectura y Escritura Especializadas"])]},
    {"nombre": "Liceo Industrial y Comercial Las Araucarias", "sufijo": "tp", "oferta": "TP", "color": "#8A4B08",
     "rut_base": 300_000, "lema": "Liceo Técnico-Profesional · Datos ficticios de demostración",
     "director": ("Héctor", "Valenzuela Campos"), "utp": ("Lorena", "Espinoza Fuentes"),
     "profesores": [("Claudio", "Mardones Rivas"), ("Verónica", "Sandoval Arce"), ("Patricio", "Leiva Toro"),
                    ("Daniela", "Carrasco Neira"), ("Gonzalo", "Pizarro Lillo")],
     "cursos": [(1, "A", "", "", None), (2, "A", "", "", None),
                (3, "A", "TP", "Administración", None), (3, "B", "TP", "Mecánica Automotriz", None),
                (4, "A", "TP", "Administración", None), (4, "B", "TP", "Mecánica Automotriz", None)]},
    {"nombre": "Liceo Polivalente Río Ñuble", "sufijo": "poli", "oferta": "POLIVALENTE", "color": "#5B2C83",
     "rut_base": 500_000, "lema": "Liceo Polivalente HC y TP · Datos ficticios de demostración",
     "director": ("Alejandra", "Muñoz Retamal"), "utp": ("Sergio", "Toledo Garrido"),
     "profesores": [("Natalia", "Fierro Jara"), ("Mauricio", "Bustos Salinas"), ("Carolina", "Reyes Méndez"),
                    ("Ignacio", "Parra Castillo"), ("Francisca", "Moya Alarcón")],
     "cursos": [(1, "A", "", "", None), (2, "A", "", "", None),
                (3, "A", "HC", "", ["Comprensión Histórica del Presente", "Taller de Literatura",
                                    "Lectura y Escritura Especializadas"]),
                (3, "B", "TP", "Gastronomía", None),
                (4, "A", "HC", "", ["Biología de los Ecosistemas", "Física", "Límites, Derivadas e Integrales"]),
                (4, "B", "TP", "Gastronomía", None)]},
]
