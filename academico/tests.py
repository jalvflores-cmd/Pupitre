from io import StringIO
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from . import importacion
from .calculos import promedio_ponderado, redondear, situacion_final
from .models import (
    Anotacion, Asignatura, AsignaturaCurso, Calificacion, Curso, Estudiante, Evaluacion, Nivel, Perfil,
)
from .rut import calcular_dv, formatear_rut, normalizar_rut, rut_es_valido


def xlsx(filas, nombre="archivo.xlsx"):
    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    return SimpleUploadedFile(nombre, salida.getvalue())


class RutTests(TestCase):
    def test_validacion(self):
        self.assertTrue(rut_es_valido("12.345.678-5"))
        self.assertTrue(rut_es_valido("123456785"))
        self.assertFalse(rut_es_valido("12.345.678-9"))
        self.assertFalse(rut_es_valido("abc"))
        self.assertEqual(calcular_dv(23040237), "K")
        self.assertTrue(rut_es_valido("23.040.237-k"))

    def test_formatos(self):
        self.assertEqual(normalizar_rut("12.345.678-5"), "12345678-5")
        self.assertEqual(formatear_rut("123456785"), "12.345.678-5")


class CalculosTests(TestCase):
    def test_redondeo_chileno(self):
        self.assertEqual(redondear(Decimal("3.95")), Decimal("4.0"))
        self.assertEqual(redondear(Decimal("3.94")), Decimal("3.9"))

    def test_ponderado(self):
        self.assertEqual(promedio_ponderado([(Decimal("4.0"), 30), (Decimal("6.0"), 70)]), Decimal("5.4"))
        self.assertIsNone(promedio_ponderado([]))

    def test_situacion_final(self):
        uno = [object()]
        self.assertEqual(situacion_final(Decimal("5.0"), []), "Promovido(a)")
        self.assertEqual(situacion_final(Decimal("4.5"), uno), "Promovido(a)")
        self.assertEqual(situacion_final(Decimal("4.4"), uno), "Reprobado(a)")
        self.assertEqual(situacion_final(Decimal("5.0"), uno * 2), "Promovido(a)")
        self.assertEqual(situacion_final(Decimal("6.0"), uno * 3), "Reprobado(a)")


class BaseDatos(TestCase):
    @classmethod
    def setUpTestData(cls):
        def usuario(nombre, rol):
            u = User.objects.create_user(nombre, password="clave-segura-123")
            Perfil.objects.create(usuario=u, rol=rol)
            return u

        cls.director = usuario("director", Perfil.Rol.DIRECTOR)
        cls.utp = usuario("utp", Perfil.Rol.UTP)
        cls.profe_mat = usuario("mate", Perfil.Rol.PROFESOR)
        cls.profe_len = usuario("lenguaje", Perfil.Rol.PROFESOR)
        nivel = Nivel.objects.create(nombre="5° Básico", orden=5)
        cls.curso = Curso.objects.create(nivel=nivel, letra="A", anio=2026, profesor_jefe=cls.profe_len)
        cls.otro_curso = Curso.objects.create(nivel=nivel, letra="B", anio=2026)
        cls.mat = AsignaturaCurso.objects.create(curso=cls.curso, asignatura=Asignatura.objects.create(nombre="Matemática"),
                                                 profesor=cls.profe_mat)
        cls.len = AsignaturaCurso.objects.create(curso=cls.curso, asignatura=Asignatura.objects.create(nombre="Lenguaje"),
                                                 profesor=cls.profe_len)
        cls.est = Estudiante.objects.create(rut="12.345.678-5", nombres="Ana", apellido_paterno="Pérez", curso=cls.curso)
        cls.est_b = Estudiante.objects.create(rut="11.111.111-1", nombres="Luis", apellido_paterno="Soto",
                                              curso=cls.otro_curso)
        ev = Evaluacion.objects.create(asignatura_curso=cls.mat, nombre="Prueba 1", semestre=1)
        Calificacion.objects.create(evaluacion=ev, estudiante=cls.est, nota=Decimal("6.0"))
        cls.ev = ev


class PermisosTests(BaseDatos):
    def test_director_y_utp_ven_todo(self):
        for u in (self.director, self.utp):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("libro_notas", args=[self.mat.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("estudiante_detalle", args=[self.est_b.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("acta_final_pdf", args=[self.curso.pk])).status_code, 200)
            self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_profesor_solo_su_asignatura(self):
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("libro_notas", args=[self.mat.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("libro_notas", args=[self.len.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("estudiante_detalle", args=[self.est_b.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("informe_final_pdf", args=[self.curso.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("estudiante_crear")).status_code, 403)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        r = self.client.get(reverse("cursos") + "?anio=2026")
        self.assertContains(r, "5° Básico A")
        self.assertNotContains(r, "5° Básico B")

    def test_profesor_jefe_ve_pero_no_edita_otras_asignaturas(self):
        self.client.force_login(self.profe_len)
        r = self.client.get(reverse("libro_notas", args=[self.mat.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="n_')
        r = self.client.post(reverse("libro_notas", args=[self.mat.pk]), {f"n_{self.est.pk}_{self.ev.pk}": "2,0"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(reverse("informe_final_pdf", args=[self.curso.pk])).status_code, 200)

    def test_detalle_estudiante_oculta_otras_asignaturas(self):
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("estudiante_detalle", args=[self.est.pk]))
        self.assertContains(r, "Matemática")
        self.assertNotContains(r, ">Lenguaje<")


class NotasTests(BaseDatos):
    def test_guardar_notas_desde_grilla(self):
        self.client.force_login(self.profe_mat)
        campo = f"n_{self.est.pk}_{self.ev.pk}"
        self.client.post(reverse("libro_notas", args=[self.mat.pk]), {campo: "5,5"})
        self.assertEqual(Calificacion.objects.get(evaluacion=self.ev, estudiante=self.est).nota, Decimal("5.5"))
        self.client.post(reverse("libro_notas", args=[self.mat.pk]), {campo: "8"})  # inválida: no cambia
        self.assertEqual(Calificacion.objects.get(evaluacion=self.ev, estudiante=self.est).nota, Decimal("5.5"))
        self.client.post(reverse("libro_notas", args=[self.mat.pk]), {campo: ""})  # vacío: borra
        self.assertFalse(Calificacion.objects.filter(evaluacion=self.ev, estudiante=self.est).exists())

    def test_leer_nota(self):
        self.assertEqual(importacion.leer_nota("5,5"), Decimal("5.5"))
        self.assertEqual(importacion.leer_nota(55), Decimal("5.5"))
        self.assertEqual(importacion.leer_nota(7), Decimal("7.0"))
        self.assertIsNone(importacion.leer_nota(""))
        with self.assertRaises(ValueError):
            importacion.leer_nota("0.5")


class ImportacionTests(BaseDatos):
    def test_importar_estudiantes_crea_y_actualiza(self):
        archivo = xlsx([
            ["RUT", "Nombres", "Apellido paterno", "Apellido materno", "Nivel", "Letra", "Año", "Teléfono apoderado"],
            ["12.345.678-5", "Ana María", "Pérez", "Soto", "5° Básico", "A", 2026, "+56911112222"],
            ["9.876.543-3", "Pedro", "Rojas", "", "6° Básico", "A", 2026, ""],
        ])
        self.client.force_login(self.utp)
        self.client.post(reverse("importar_estudiantes"), {"archivo": archivo})
        self.assertEqual(Estudiante.objects.get(rut="12345678-5").nombres, "Ana María")
        pedro = Estudiante.objects.get(rut="9876543-3")
        self.assertEqual(str(pedro.curso.nivel), "6° Básico")

    def test_importar_estudiantes_con_error_no_guarda_nada(self):
        archivo = xlsx([["RUT", "Nombres", "Apellido paterno"], ["9.876.543-3", "Pedro", "Rojas"],
                        ["12.345.678-0", "Malo", "Rut"]])
        self.client.force_login(self.director)
        r = self.client.post(reverse("importar_estudiantes"), {"archivo": archivo}, follow=True)
        self.assertContains(r, "no válido")
        self.assertFalse(Estudiante.objects.filter(rut="9876543-3").exists())

    def test_profesor_no_importa_estudiantes(self):
        self.client.force_login(self.profe_mat)
        r = self.client.post(reverse("importar_estudiantes"), {"archivo": xlsx([["RUT"]])})
        self.assertEqual(r.status_code, 403)

    def test_plantilla_de_notas_ida_y_vuelta(self):
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("plantilla_notas", args=["notas", self.mat.pk]))
        libro = load_workbook(BytesIO(r.content))
        hoja = libro.worksheets[0]
        self.assertEqual(hoja.cell(1, 3).value, "Prueba 1")
        self.assertEqual(hoja.cell(4, 1).value, "12.345.678-5")
        hoja.cell(4, 3, 4.5)
        hoja.cell(1, 4, "Prueba 2")
        hoja.cell(2, 4, 2)
        hoja.cell(3, 4, 1)
        hoja.cell(4, 4, "6,8")
        salida = BytesIO()
        libro.save(salida)
        r = self.client.post(reverse("importar_notas", args=[self.mat.pk]),
                             {"archivo": SimpleUploadedFile("n.xlsx", salida.getvalue())})
        self.assertEqual(Calificacion.objects.get(evaluacion=self.ev, estudiante=self.est).nota, Decimal("4.5"))
        nueva = Evaluacion.objects.get(asignatura_curso=self.mat, nombre="Prueba 2")
        self.assertEqual(nueva.semestre, 2)
        self.assertEqual(Calificacion.objects.get(evaluacion=nueva).nota, Decimal("6.8"))

    def test_importar_notas_de_estudiante_ajeno_falla(self):
        self.client.force_login(self.profe_mat)
        archivo = xlsx([["RUT", "Estudiante", "Prueba 1"], ["Semestre", "", 1], ["Ponderación", "", 1],
                        ["11.111.111-1", "Luis", 7]])
        r = self.client.post(reverse("importar_notas", args=[self.mat.pk]), {"archivo": archivo}, follow=True)
        self.assertContains(r, "no corresponde a un estudiante del curso")

    def test_importar_anotaciones(self):
        self.client.force_login(self.profe_mat)
        archivo = xlsx([["RUT", "Fecha", "Tipo", "Gravedad", "Asignatura", "Descripción"],
                        ["12.345.678-5", "20-05-2026", "Negativa", "Leve", "Matemática", "Interrumpe la clase"],
                        ["12.345.678-5", "21-05-2026", "positiva", "", "", "Ayuda a sus compañeros"]])
        self.client.post(reverse("importar_anotaciones"), {"archivo": archivo})
        self.assertEqual(Anotacion.objects.filter(estudiante=self.est).count(), 2)
        self.assertEqual(Anotacion.objects.get(tipo="NEGATIVA").gravedad, "LEVE")


class ExportacionTests(BaseDatos):
    def test_informes(self):
        self.client.force_login(self.director)
        for nombre, tipo in [("informe_notas_pdf", "application/pdf"), ("informe_final_pdf", "application/pdf"),
                             ("acta_final_pdf", "application/pdf"), ("informe_final_excel", "spreadsheetml")]:
            r = self.client.get(reverse(nombre, args=[self.curso.pk]))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertIn(tipo, r["Content-Type"])
        r = self.client.get(reverse("informe_final_excel", args=[self.curso.pk]))
        hoja = load_workbook(BytesIO(r.content)).worksheets[0]
        self.assertEqual(hoja.cell(6, 3).value, "Pérez, Ana")
        self.assertEqual(hoja.cell(5, 5).value, "Matemática")
        self.assertEqual(hoja.cell(6, 5).value, 6.0)

    def test_anotacion_desde_ficha(self):
        self.client.force_login(self.profe_mat)
        self.client.post(reverse("anotacion_crear", args=[self.est.pk]),
                         {"fecha": "2026-05-01", "tipo": "POSITIVA", "descripcion": "Excelente trabajo"})
        a = Anotacion.objects.get()
        self.assertEqual(a.autor, self.profe_mat)


class SolicitudCambioTests(BaseDatos):
    def datos(self, **cambios):
        base = {"rut": "12.345.678-5", "nombres": "Ana", "apellido_paterno": "Pérez", "motivo": "Corrección"}
        base.update(cambios)
        return base

    def test_profesor_jefe_solicita_y_no_se_aplica_hasta_aprobar(self):
        from .models import SolicitudCambio
        self.client.force_login(self.profe_len)  # jefe del 5° A
        self.client.post(reverse("solicitud_crear", args=[self.est.pk]),
                         self.datos(nombres="Ana María", direccion="Los Aromos 12"))
        self.est.refresh_from_db()
        self.assertEqual(self.est.nombres, "Ana")
        s = SolicitudCambio.objects.get()
        self.assertEqual(set(s.cambios), {"nombres", "direccion"})
        self.assertEqual(s.cambios["nombres"], {"antes": "Ana", "despues": "Ana María"})
        # El profesor jefe no puede aprobar su propia solicitud
        self.assertEqual(self.client.post(reverse("solicitud_resolver", args=[s.pk]), {"accion": "aprobar"}).status_code, 403)
        self.client.force_login(self.utp)
        self.client.post(reverse("solicitud_resolver", args=[s.pk]), {"accion": "aprobar"})
        self.est.refresh_from_db()
        self.assertEqual((self.est.nombres, self.est.direccion), ("Ana María", "Los Aromos 12"))
        s.refresh_from_db()
        self.assertEqual((s.estado, s.revisor), ("APROBADA", self.utp))

    def test_rechazo_no_cambia_datos(self):
        from .models import SolicitudCambio
        self.client.force_login(self.profe_len)
        self.client.post(reverse("solicitud_crear", args=[self.est.pk]), self.datos(nombres="Otra"))
        s = SolicitudCambio.objects.get()
        self.client.force_login(self.director)
        self.client.post(reverse("solicitud_resolver", args=[s.pk]), {"accion": "rechazar", "comentario": "No corresponde"})
        self.est.refresh_from_db()
        self.assertEqual(self.est.nombres, "Ana")
        s.refresh_from_db()
        self.assertEqual((s.estado, s.comentario_revision), ("RECHAZADA", "No corresponde"))

    def test_solo_profesor_jefe_puede_solicitar(self):
        self.client.force_login(self.profe_mat)  # no es jefe del curso
        self.assertEqual(self.client.get(reverse("solicitud_crear", args=[self.est.pk])).status_code, 403)
        self.client.force_login(self.profe_len)
        self.assertEqual(self.client.get(reverse("estudiante_editar", args=[self.est.pk])).status_code, 403)
        r = self.client.get(reverse("estudiante_detalle", args=[self.est.pk]))
        self.assertContains(r, "Solicitar modificación")

    def test_rut_invalido_no_genera_solicitud(self):
        from .models import SolicitudCambio
        self.client.force_login(self.profe_len)
        self.client.post(reverse("solicitud_crear", args=[self.est.pk]), self.datos(rut="12.345.678-0"))
        self.assertFalse(SolicitudCambio.objects.exists())


class RolesAdicionalesTests(BaseDatos):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        def usuario(nombre, rol):
            u = User.objects.create_user(nombre, password="clave-segura-123")
            Perfil.objects.create(usuario=u, rol=rol)
            return u
        cls.sostenedor = usuario("sostenedor", Perfil.Rol.SOSTENEDOR)
        cls.inspector = usuario("inspector", Perfil.Rol.INSPECTOR)
        cls.convivencia = usuario("convivencia", Perfil.Rol.CONVIVENCIA)

    def test_sostenedor_ve_todo_sin_modificar(self):
        self.client.force_login(self.sostenedor)
        r = self.client.get(reverse("libro_notas", args=[self.mat.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="n_')
        self.assertEqual(self.client.get(reverse("estudiante_detalle", args=[self.est_b.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("acta_final_pdf", args=[self.curso.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("libro_notas", args=[self.mat.pk]),
                                          {f"n_{self.est.pk}_{self.ev.pk}": "2,0"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("anotacion_crear", args=[self.est.pk]),
                                          {"fecha": "2026-05-01", "tipo": "POSITIVA", "descripcion": "x"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("estudiante_editar", args=[self.est.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("solicitud_crear", args=[self.est.pk])).status_code, 403)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_convivencia_e_inspector(self):
        for u in (self.inspector, self.convivencia):
            self.client.force_login(u)
            # Ven notas de todos los cursos, sin editarlas
            r = self.client.get(reverse("libro_notas", args=[self.mat.pk]))
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'name="n_')
            # Anotan en cualquier curso
            self.client.post(reverse("anotacion_crear", args=[self.est_b.pk]),
                             {"fecha": "2026-05-01", "tipo": "NEGATIVA", "gravedad": "GRAVE", "descripcion": "Pelea"})
            # Editan contacto directo, pero no el nombre
            self.client.post(reverse("estudiante_contacto", args=[self.est_b.pk]),
                             {"apoderado_telefono": f"+56 9 {u.pk}"})
            self.est_b.refresh_from_db()
            self.assertEqual(self.est_b.apoderado_telefono, f"+56 9 {u.pk}")
            self.assertEqual(self.client.get(reverse("estudiante_editar", args=[self.est_b.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("solicitud_crear", args=[self.est_b.pk])).status_code, 200)
        self.assertEqual(Anotacion.objects.filter(estudiante=self.est_b).count(), 2)
        # Pueden eliminar anotaciones de otros
        a = Anotacion.objects.filter(autor=self.inspector).get()
        self.client.post(reverse("anotacion_eliminar", args=[a.pk]))
        self.assertFalse(Anotacion.objects.filter(pk=a.pk).exists())

    def test_profesor_no_edita_contacto(self):
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("estudiante_contacto", args=[self.est.pk])).status_code, 403)

    def test_comentarios(self):
        from .models import Comentario
        self.client.force_login(self.profe_mat)
        self.client.post(reverse("comentario_enviar"), {"texto": "Me gusta", "tipo": "SUGERENCIA", "pagina": "/cursos/"})
        self.client.post(reverse("comentario_enviar"), {"texto": "x", "pagina": "javascript:alert(1)"})
        self.assertEqual(Comentario.objects.count(), 2)
        self.assertEqual(Comentario.objects.get(texto="x").pagina, "")
        self.assertEqual(self.client.get(reverse("comentarios")).status_code, 403)
        self.client.force_login(self.director)
        self.assertContains(self.client.get(reverse("comentarios")), "Me gusta")


class FuncionariosTests(BaseDatos):
    def crear(self, **extra):
        from .models import Funcionario
        datos = {"rut": "12.345.678-5", "nombres": "Rosa", "apellido_paterno": "Díaz", "horas_contrato": Decimal("44"),
                 "cargo": "DOCENTE"}
        datos.update(extra)
        return Funcionario.objects.create(**datos)

    def test_distribucion_ley_20903(self):
        from .models import Establecimiento
        est = Establecimiento.objects.create(nombre="Escuela", alta_concentracion=True)
        f = self.crear(primer_ciclo=True)
        self.assertEqual(f.distribucion(est), (60, Decimal("26.40"), Decimal("17.60")))
        f.primer_ciclo = False
        self.assertEqual(f.distribucion(est), (65, Decimal("28.60"), Decimal("15.40")))
        est.alta_concentracion = False
        f.primer_ciclo = True
        self.assertEqual(f.distribucion(est)[0], 65)
        f.proporcion = "60"
        self.assertEqual(f.distribucion(est)[0], 60)
        f.proporcion, f.cargo = "AUTO", "ASISTENTE"
        self.assertEqual(f.distribucion(est), (None, None, None))

    def test_acceso(self):
        self.crear()
        self.client.force_login(self.director)
        r = self.client.get(reverse("funcionarios"))
        self.assertContains(r, "Rosa Díaz")
        self.assertContains(r, "28 h 36 min")
        self.assertEqual(self.client.get(reverse("funcionarios") + "?exportar=excel").status_code, 200)
        r = self.client.post(reverse("funcionario_crear"), {
            "rut": "9.876.543-3", "nombres": "Luis", "apellido_paterno": "Soto", "cargo": "DOCENTE",
            "tipo_contrato": "CONTRATA", "horas_contrato": "30", "proporcion": "AUTO", "activo": "on"})
        self.assertEqual(r.status_code, 302)
        self.client.post(reverse("prioritarios"), {"alta_concentracion": "on"})
        from .models import Establecimiento
        self.assertTrue(Establecimiento.actual().alta_concentracion)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("funcionarios")).status_code, 403)
        self.assertEqual(self.client.post(reverse("prioritarios"), {}).status_code, 403)


class DemoYListadoTests(BaseDatos):
    def test_datos_demo_no_pisa_cambios(self):
        from django.core.management import call_command
        from .models import Establecimiento
        Establecimiento.objects.create(nombre="Escuela Gabriela Mistral", director="Nombre editado")
        call_command("datos_demo", stdout=StringIO())
        u = User.objects.get(username="director")
        u.perfil.rol = Perfil.Rol.UTP
        u.perfil.save()
        call_command("datos_demo", stdout=StringIO())
        self.assertEqual(Establecimiento.actual().director, "Nombre editado")
        self.assertEqual(User.objects.get(username="director").perfil.rol, Perfil.Rol.UTP)

    def test_estudiantes_agrupados_por_curso(self):
        self.client.force_login(self.director)
        r = self.client.get(reverse("estudiantes"))
        html = r.content.decode()
        self.assertLess(html.index("5° Básico A"), html.index("5° Básico B"))
        self.assertLess(html.index("Pérez, Ana"), html.index("Soto, Luis"))


SIGE_HTML = """<!DOCTYPE html><html><head><title>.:SIGE:.</title></head><body><table>
<tr><td>Año</td><td>RBD</td><td>Cod Tipo Enseñanza</td><td>Cod Grado</td><td>Desc Grado</td><td>Letra Curso</td>
<td>Run</td><td>Dígito Ver.</td><td>Genero</td><td>Nombres</td><td>Apellido Paterno</td><td>Apellido Materno</td>
<td>Dirección</td><td>Comuna Residencia</td><td>Código Comuna Residencia</td><td>Email</td><td>Telefono</td>
<td>Celular</td><td>Fecha Nacimiento</td><td>Código Etnia</td><td>Fecha Incorporación Curso</td><td>Fecha Retiro</td>
<td>%Asistenca</td><td>Promedio Final</td></tr>
<tr><td>2026</td><td>3660</td><td>10</td><td>4</td><td>1er nivel de Transición (Pre-kinder)</td><td>A</td><td>22222222</td>
<td>2</td><td>F</td><td>MARÍA DE LOS ÁNGELES</td><td>PÉREZ</td><td>SOTO</td><td>CALLE UNO 123</td><td>CHILLÁN</td>
<td>16101</td><td></td><td></td><td>912345678</td><td>2021-05-11</td><td>0</td><td>2026-03-01</td><td>1900-01-01</td><td>0</td><td>0.0</td></tr>
<tr><td>2026</td><td>3660</td><td>110</td><td>5</td><td>5° básico</td><td>A</td><td>100502822</td>
<td>8</td><td>M</td><td>JUAN</td><td>ROJAS</td><td>DÍAZ</td><td></td><td>CHILLÁN VIEJO</td>
<td>16103</td><td></td><td></td><td></td><td>2015-02-01</td><td>0</td><td>2026-03-01</td><td>2026-04-30</td><td>91.5</td><td>5.8</td></tr>
</table></body></html>"""


class SigeYFormatosTests(BaseDatos):
    def subir(self, contenido, nombre, usuario=None):
        self.client.force_login(usuario or self.utp)
        return self.client.post(reverse("importar_estudiantes"),
                                {"archivo": SimpleUploadedFile(nombre, contenido)}, follow=True)

    def test_nomina_sige_tal_como_viene(self):
        r = self.subir(SIGE_HTML.encode("latin-1"), "nomina_excel.xls")
        self.assertContains(r, "Nómina SIGE reconocida")
        maria = Estudiante.objects.get(rut="22222222-2")
        self.assertEqual((maria.nombres, maria.apellido_paterno, maria.comuna), ("María de los Ángeles", "Pérez", "Chillán"))
        self.assertEqual((maria.genero, maria.celular, maria.codigo_comuna), ("F", "912345678", "16101"))
        self.assertEqual(maria.curso.nivel.nombre, "Pre-kínder")
        self.assertTrue(maria.activo)
        juan = Estudiante.objects.get(rut="100502822-8")  # IPE de 9 dígitos
        self.assertFalse(juan.activo)
        self.assertEqual((juan.porcentaje_asistencia, juan.promedio_sige), (Decimal("91.5"), Decimal("5.8")))
        self.assertEqual(juan.curso.nivel.nombre, "5° Básico")  # se reutiliza el nivel existente
        self.assertEqual(juan.curso.nivel.orden, 7)

    def test_rbd_de_otro_establecimiento(self):
        from .models import Establecimiento
        Establecimiento.objects.create(nombre="Otra", rbd="9999")
        r = self.subir(SIGE_HTML.encode("latin-1"), "nomina.xls")
        self.assertContains(r, "no corresponde a este establecimiento")
        self.assertFalse(Estudiante.objects.filter(rut="22222222-2").exists())

    def test_profesor_jefe_solo_su_curso(self):
        r = self.subir(SIGE_HTML.encode("latin-1"), "nomina.xls", self.profe_len)  # jefe del 5° A (2026)
        self.assertContains(r, "no es de su jefatura")
        self.assertEqual(self.subir(b"x", "a.csv", self.profe_mat).status_code, 403)  # no es jefe

    def test_csv_y_docx(self):
        csv_txt = "RUT;Nombres;Apellido paterno;Nivel;Letra;Año\n9.876.543-3;Pedro;Rojas;6° Básico;A;2026\n"
        self.subir(csv_txt.encode("cp1252"), "lista.csv")
        self.assertTrue(Estudiante.objects.filter(rut="9876543-3").exists())
        import docx
        documento = docx.Document()
        tabla = documento.add_table(rows=2, cols=3)
        for i, v in enumerate(["RUT", "Nombres", "Apellido paterno"]):
            tabla.cell(0, i).text = v
        for i, v in enumerate(["7.654.321-6", "Rosa", "Vera"]):
            tabla.cell(1, i).text = v
        salida = BytesIO()
        documento.save(salida)
        self.subir(salida.getvalue(), "lista.docx")
        self.assertTrue(Estudiante.objects.filter(rut="7654321-6").exists())

    def test_certificado_y_acta(self):
        from .calculos import nota_en_palabras
        self.assertEqual(nota_en_palabras(Decimal("6.5")), "seis coma cinco")
        self.client.force_login(self.director)
        for nombre in ("informe_final_pdf", "acta_final_pdf", "informe_notas_pdf"):
            self.assertEqual(self.client.get(reverse(nombre, args=[self.curso.pk])).status_code, 200)


class TalleresYConceptosTests(BaseDatos):
    def test_religion_no_incide_en_promedio(self):
        from .calculos import resumen_curso
        rel = AsignaturaCurso.objects.create(curso=self.curso, profesor=self.profe_mat,
                                             asignatura=Asignatura.objects.create(nombre="Religión", incide_en_promedio=False))
        ev = Evaluacion.objects.create(asignatura_curso=rel, nombre="R1")
        Calificacion.objects.create(evaluacion=ev, estudiante=self.est, nota=Decimal("2.0"))
        _, _, resumenes = resumen_curso(self.curso)
        r = resumenes[0]
        self.assertEqual(r.promedio_general, Decimal("6.0"))  # solo Matemática
        self.assertEqual(r.situacion, "Promovido(a)")
        self.assertEqual([p.concepto for p in r.asignaturas if not p.incide], ["I"])

    def test_crear_taller_jec(self):
        self.client.force_login(self.utp)
        self.client.post(reverse("talleres"), {"nombre": "Taller de Ajedrez", "cursos": [self.curso.pk, self.otro_curso.pk],
                                               "profesor": self.profe_mat.pk, "horas_semanales": "2"})
        talleres = AsignaturaCurso.objects.filter(asignatura__nombre="Taller de Ajedrez")
        self.assertEqual(talleres.count(), 2)
        self.assertEqual(talleres.first().asignatura.tipo, "TALLER")
        self.assertFalse(talleres.first().asignatura.incide_en_promedio)
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("talleres"))
        self.assertContains(r, "Taller de Ajedrez")
        self.assertEqual(self.client.post(reverse("talleres"), {"nombre": "x"}).status_code, 403)
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(reverse("informe_final_pdf", args=[self.curso.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("acta_final_pdf", args=[self.curso.pk])).status_code, 200)
