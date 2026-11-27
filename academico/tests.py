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
        Establecimiento.objects.order_by("pk").update(nombre="Escuela Gabriela Mistral", director="Nombre editado")
        call_command("datos_demo", stdout=StringIO())
        u = User.objects.get(username="director")
        u.perfil.rol = Perfil.Rol.UTP
        u.perfil.save()
        call_command("datos_demo", stdout=StringIO())
        self.assertEqual(Establecimiento.objects.order_by("pk").first().director, "Nombre editado")
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
        Establecimiento.objects.update(rbd="9999")
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
        no_incide = [p for p in r.asignaturas if not p.incide]
        self.assertEqual([p.final for p in no_incide], [Decimal("2.0")])  # se califica con nota
        self.assertFalse(no_incide[0].con_concepto)

    def test_religion_segun_credo(self):
        from .calculos import resumen_curso
        from .models import Religion
        cat = AsignaturaCurso.objects.create(curso=self.curso, profesor=self.profe_mat, asignatura=Asignatura.objects.create(
            nombre="Religión Católica", incide_en_promedio=False, religion=Religion.CATOLICA))
        evg = AsignaturaCurso.objects.create(curso=self.curso, profesor=self.profe_mat, asignatura=Asignatura.objects.create(
            nombre="Religión Evangélica", incide_en_promedio=False, religion=Religion.EVANGELICA))
        self.est.religion = Religion.EVANGELICA
        self.est.save()
        Calificacion.objects.create(evaluacion=Evaluacion.objects.create(asignatura_curso=evg, nombre="E1"),
                                    estudiante=self.est, nota=Decimal("6.5"))
        self.assertTrue(self.est.cursa(evg.asignatura))
        self.assertFalse(self.est.cursa(cat.asignatura))
        _, _, resumenes = resumen_curso(self.curso)
        filas = {p.asignatura_curso.asignatura.nombre: p for p in resumenes[0].asignaturas}
        self.assertFalse(filas["Religión Católica"].aplica)
        self.assertEqual(filas["Religión Evangélica"].final, Decimal("6.5"))
        self.client.force_login(self.director)
        for nombre in ("informe_final_pdf", "acta_final_pdf", "informe_notas_pdf"):
            self.assertEqual(self.client.get(reverse(nombre, args=[self.curso.pk])).status_code, 200)
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("libro_notas", args=[cat.pk]))
        self.assertNotContains(r, "Ana")

    def test_taller_con_nota_incide(self):
        from .calculos import resumen_curso
        taller = AsignaturaCurso.objects.create(curso=self.curso, profesor=self.profe_mat, asignatura=Asignatura.objects.create(
            nombre="Taller de Robótica", tipo=Asignatura.Tipo.TALLER, incide_en_promedio=True))
        Calificacion.objects.create(evaluacion=Evaluacion.objects.create(asignatura_curso=taller, nombre="T1"),
                                    estudiante=self.est, nota=Decimal("7.0"))
        _, _, resumenes = resumen_curso(self.curso)
        self.assertEqual(resumenes[0].promedio_general, Decimal("6.5"))

    def test_crear_taller_jec_desde_el_curso(self):
        self.client.force_login(self.utp)
        r = self.client.get(reverse("curso_detalle", args=[self.curso.pk]))
        self.assertContains(r, "Agregar asignatura o taller JEC")
        self.client.post(reverse("curso_asignatura_agregar", args=[self.curso.pk]), {
            "nuevo_taller": "Taller de Ajedrez", "profesor": self.profe_mat.pk, "horas_semanales": "2",
            "incide_en_promedio": "on", "todo_el_nivel": "on"})
        talleres = AsignaturaCurso.objects.filter(asignatura__nombre="Taller de Ajedrez")
        self.assertEqual(talleres.count(), 2)  # el curso y el otro curso del mismo nivel
        taller = talleres.get(curso=self.curso)
        self.assertEqual(taller.asignatura.tipo, "TALLER")
        self.assertTrue(taller.asignatura.incide_en_promedio)
        # cambiar profesor y horas desde la carga académica del curso
        self.client.post(reverse("curso_carga_guardar", args=[self.curso.pk]),
                         {f"profesor_{taller.pk}": self.utp.pk, f"horas_{taller.pk}": "3,5"})
        taller.refresh_from_db()
        self.assertEqual((taller.profesor, taller.horas_semanales), (self.utp, Decimal("3.5")))
        # no se puede agregar una asignatura del plan escribiéndola como taller
        self.client.post(reverse("curso_asignatura_agregar", args=[self.curso.pk]), {"nuevo_taller": "matemática"})
        self.assertEqual(Asignatura.objects.filter(nombre__iexact="matemática").count(), 1)
        self.client.force_login(self.profe_len)  # profesora jefe: ve todo el curso, sin editar la carga
        r = self.client.get(reverse("curso_detalle", args=[self.curso.pk]))
        self.assertContains(r, "Talleres JEC")
        self.assertNotContains(r, "Agregar asignatura o taller JEC")
        self.assertEqual(self.client.post(reverse("curso_asignatura_agregar", args=[self.curso.pk]),
                                          {"nuevo_taller": "x"}).status_code, 403)
        otro = talleres.get(curso=self.otro_curso)
        self.client.force_login(self.utp)
        self.client.post(reverse("curso_asignatura_quitar", args=[otro.pk]))
        self.assertFalse(AsignaturaCurso.objects.filter(pk=otro.pk).exists())
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(reverse("informe_final_pdf", args=[self.curso.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("acta_final_pdf", args=[self.curso.pk])).status_code, 200)


class ConvivenciaDerivacionesTests(BaseDatos):
    def _usuario(self, nombre, rol):
        u = User.objects.create_user(nombre, password="x")
        Perfil.objects.create(usuario=u, rol=rol)
        return u

    def test_falta_grave_se_deriva_y_convivencia_activa_protocolo(self):
        from .models import Anotacion
        self.client.force_login(self.profe_mat)
        self.client.post(reverse("anotacion_crear", args=[self.est.pk]), {
            "fecha": "2026-09-01", "tipo": "NEGATIVA", "gravedad": "GRAVE", "descripcion": "Agrede a un compañero."})
        a = Anotacion.objects.get(estudiante=self.est)
        self.assertTrue(a.derivada)
        self.assertEqual(a.estado_derivacion, "PENDIENTE")
        # el profesor de asignatura no gestiona la derivación
        self.assertEqual(self.client.get(reverse("anotacion_derivacion", args=[a.pk])).status_code, 403)
        conv = self._usuario("conv", Perfil.Rol.CONVIVENCIA)
        self.client.force_login(conv)
        self.client.post(reverse("anotacion_derivacion", args=[a.pk]), {
            "derivada": "on", "estado_derivacion": "EN_PROCESO", "protocolo": "MALTRATO_ESTUDIANTES",
            "seguimiento": "Se cita a apoderados."})
        a.refresh_from_db()
        self.assertEqual((a.estado_derivacion, a.protocolo), ("EN_PROCESO", "MALTRATO_ESTUDIANTES"))
        r = self.client.get(reverse("convivencia") + "?derivadas=PROTOCOLO")
        self.assertContains(r, "Maltrato, acoso escolar")

    def test_leve_no_se_deriva_salvo_que_se_marque(self):
        from .models import Anotacion
        self.client.force_login(self.profe_mat)
        self.client.post(reverse("anotacion_crear", args=[self.est.pk]), {
            "fecha": "2026-09-01", "tipo": "NEGATIVA", "gravedad": "LEVE", "descripcion": "Sin materiales."})
        self.client.post(reverse("anotacion_crear", args=[self.est.pk]), {
            "fecha": "2026-09-02", "tipo": "OBSERVACION", "descripcion": "Se ve triste.", "derivada": "on"})
        self.assertEqual(list(Anotacion.objects.order_by("fecha").values_list("derivada", flat=True)), [False, True])

    def test_redes_y_entrevistas_solo_para_quienes_corresponde(self):
        from .models import Entrevista, RedApoyo
        conv = self._usuario("conv", Perfil.Rol.CONVIVENCIA)
        sost = self._usuario("sost", Perfil.Rol.SOSTENEDOR)
        self.client.force_login(conv)
        self.client.post(reverse("red_crear", args=[self.est.pk]), {
            "institucion": "OLN", "programa": "OLN Chillán", "vigente": "on"})
        self.assertEqual(RedApoyo.objects.filter(estudiante=self.est).count(), 1)
        self.client.post(reverse("entrevista_crear", args=[self.est.pk]), {
            "tipo": "APODERADO", "fecha": "2026-09-03", "entrevistado": "María Pérez", "parentesco": "Madre",
            "rut_entrevistado": "22222222-2", "motivo": "Conversar sobre conducta.", "desarrollo": "Relato <b>x</b>"})
        e = Entrevista.objects.get(estudiante=self.est)
        self.assertEqual(e.entrevistador, conv)
        r = self.client.get(reverse("entrevista_pdf", args=[e.pk]))
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(self.client.get(reverse("entrevista_formato_pdf", args=[self.est.pk])).status_code, 200)
        # profesor(a) jefe: ve redes y entrevistas de su curso y puede registrar entrevistas
        self.client.force_login(self.profe_len)
        r = self.client.get(reverse("estudiante_detalle", args=[self.est.pk]))
        self.assertContains(r, "OLN Chillán")
        self.assertContains(r, "María Pérez")
        self.assertEqual(self.client.get(reverse("entrevista_pdf", args=[e.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("entrevista_crear", args=[self.est.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("red_crear", args=[self.est.pk])).status_code, 403)
        # profesor(a) de asignatura y sostenedor: no ven datos sensibles
        for u in (self.profe_mat, sost):
            self.client.force_login(u)
            r = self.client.get(reverse("estudiante_detalle", args=[self.est.pk]))
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, "OLN Chillán")
            self.assertNotContains(r, "María Pérez")
            self.assertEqual(self.client.get(reverse("entrevista_pdf", args=[e.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("entrevista_crear", args=[self.est.pk])).status_code, 403)


class InstalacionLocalTests(TestCase):
    def setUp(self):
        from . import primera_vez
        primera_vez._configurada = False

    def test_asistente_de_primera_configuracion(self):
        from .models import Establecimiento
        r = self.client.get("/cursos/")
        self.assertRedirects(r, reverse("bienvenida"), fetch_redirect_response=False)
        r = self.client.post(reverse("bienvenida"), {
            "nombre": "Escuela Rural Los Aromos", "rbd": "12345", "comuna": "Chillán", "region": "Ñuble",
            "director": "", "jefe_utp": "", "rol": "DIRECTOR", "nombres": "Jorge", "apellidos": "Sandoval Morales",
            "usuario": "jsandoval", "clave1": "Escuela-2026!", "clave2": "Escuela-2026!", "plan_oficial": "on"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        est = Establecimiento.objects.get()
        self.assertEqual((est.nombre, est.director), ("Escuela Rural Los Aromos", "Jorge Sandoval Morales"))
        u = User.objects.get(username="jsandoval")
        self.assertTrue(u.is_superuser)
        self.assertEqual(u.perfil.rol, "DIRECTOR")
        self.assertTrue(Asignatura.objects.filter(nombre="Religión Evangélica", religion="EVANGELICA").exists())
        self.assertEqual(self.client.get("/cursos/").status_code, 200)
        self.assertRedirects(self.client.get(reverse("bienvenida")), reverse("inicio"), fetch_redirect_response=False)

    def test_cargar_plan_oficial(self):
        from .models import Perfil
        u = User.objects.create_user("utp", password="x")
        Perfil.objects.create(usuario=u, rol="UTP")
        quinto = Curso.objects.create(nivel=Nivel.objects.create(nombre="5° Básico", orden=7), letra="A", anio=2026)
        kinder = Curso.objects.create(nivel=Nivel.objects.create(nombre="Kínder", orden=2), letra="A", anio=2026)
        self.client.force_login(u)
        from unittest import mock
        with mock.patch("academico.views.anio_actual", return_value=2026):
            self.client.post(reverse("cargar_plan_oficial"))
        self.assertEqual(quinto.asignaturas_curso.count(), 12)
        self.assertEqual(kinder.asignaturas_curso.count(), 0)
        self.assertEqual(quinto.asignaturas_curso.get(asignatura__nombre="Matemática").horas_semanales, 6)
        self.client.post(reverse("cargar_plan_oficial_curso", args=[quinto.pk]))  # no duplica
        self.assertEqual(quinto.asignaturas_curso.count(), 12)


class ConfiguracionEditableTests(BaseDatos):
    def _logo(self):
        from PIL import Image
        b = BytesIO()
        Image.new("RGB", (300, 150), (200, 30, 30)).save(b, format="PNG")
        return SimpleUploadedFile("logo.png", b.getvalue(), content_type="image/png")

    def test_logo_color_y_listas(self):
        from .models import Establecimiento, OpcionCatalogo
        self.client.force_login(self.utp)
        r = self.client.post(reverse("configuracion"), {
            "seccion": "escuela", "nombre": "Escuela Los Aromos", "color_principal": "#7A1F3D",
            "pie_documentos": "Educar con cariño", "logo_archivo": self._logo()})
        self.assertRedirects(r, reverse("configuracion"), fetch_redirect_response=False)
        est = Establecimiento.objects.order_by("pk").first()
        self.assertTrue(est.logo)
        self.assertEqual(est.color_principal, "#7A1F3D")
        self.assertEqual(self.client.get(reverse("logo"))["Content-Type"], "image/png")
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "--p-azul: #7A1F3D")
        self.assertContains(r, "/logo.png?v=")
        # Excel interno con logo y pie
        xl = self.client.get(reverse("informe_final_excel", args=[self.curso.pk]))
        libro = load_workbook(BytesIO(xl.content))
        self.assertEqual(len(libro.active._images), 1)
        self.assertEqual(libro.active["A4"].value, "Educar con cariño")
        # documentos oficiales sin cambios (se generan igual)
        self.assertEqual(self.client.get(reverse("acta_final_pdf", args=[self.curso.pk])).status_code, 200)
        # listas editables: renombrar un protocolo y agregar uno nuevo
        prot = OpcionCatalogo.objects.filter(tipo="PROTOCOLO")
        datos = {"seccion": "PROTOCOLO", "protocolo-TOTAL_FORMS": prot.count() + 1,
                 "protocolo-INITIAL_FORMS": prot.count(), "protocolo-MIN_NUM_FORMS": 0, "protocolo-MAX_NUM_FORMS": 1000}
        for i, o in enumerate(prot):
            datos[f"protocolo-{i}-id"] = o.pk
            datos[f"protocolo-{i}-nombre"] = "Protocolo de bullying" if o.codigo == "MALTRATO_ESTUDIANTES" else o.nombre
            if o.codigo != "ACCIDENTE":
                datos[f"protocolo-{i}-activo"] = "on"
        datos[f"protocolo-{prot.count()}-nombre"] = "Protocolo de salidas pedagógicas"
        datos[f"protocolo-{prot.count()}-activo"] = "on"
        self.client.post(reverse("configuracion"), datos)
        self.assertTrue(OpcionCatalogo.objects.filter(nombre="Protocolo de salidas pedagógicas", tipo="PROTOCOLO").exists())
        self.assertFalse(OpcionCatalogo.objects.get(codigo="ACCIDENTE").activo)
        from .forms import DerivacionForm
        opciones = dict(DerivacionForm().fields["protocolo"].choices)
        self.assertEqual(opciones["MALTRATO_ESTUDIANTES"], "Protocolo de bullying")
        self.assertNotIn("ACCIDENTE", opciones)
        # profesores no acceden a la configuración
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("configuracion")).status_code, 403)


class VariosEstablecimientosTests(TestCase):
    """Cada establecimiento ve solo sus datos; el superadministrador administra la plataforma."""

    @classmethod
    def setUpTestData(cls):
        from .models import Establecimiento
        from .tenencia import en_establecimiento

        cls.a = Establecimiento.objects.order_by("pk").first() or Establecimiento.objects.create(nombre="A")
        cls.b = Establecimiento.objects.create(nombre="Liceo B", oferta="TP")

        def poblar(est, sufijo, rut):
            with en_establecimiento(est):
                u = User.objects.create_user(f"utp.{sufijo}", password="x")
                Perfil.objects.create(usuario=u, rol="UTP", establecimiento=est)
                nivel, _ = Nivel.objects.get_or_create(nombre="I Medio", defaults={"orden": 11, "ensenanza": "MEDIA"})
                curso = Curso.objects.create(nivel=nivel, letra="A", anio=2026)
                ac = AsignaturaCurso.objects.create(curso=curso, asignatura=Asignatura.objects.create(nombre="Matemática"),
                                                    profesor=u)
                e = Estudiante.objects.create(rut=rut, nombres=f"Est {sufijo}", apellido_paterno="X", curso=curso)
                return u, curso, ac, e

        cls.ua, cls.ca, cls.aca, cls.ea = poblar(cls.a, "a", "12.345.678-5")
        cls.ub, cls.cb, cls.acb, cls.eb = poblar(cls.b, "b", "12.345.678-5")  # mismo RUT en otro colegio: permitido
        cls.sa = User.objects.create_user("superadmin", password="x")
        Perfil.objects.create(usuario=cls.sa, rol="SUPERADMIN")

    def test_no_se_ven_datos_de_otro_establecimiento(self):
        self.client.force_login(self.ua)
        r = self.client.get(reverse("estudiantes"))
        self.assertContains(r, "Est a")
        self.assertNotContains(r, "Est b")
        for nombre, pk in (("estudiante_detalle", self.eb.pk), ("curso_detalle", self.cb.pk),
                           ("libro_notas", self.acb.pk), ("acta_final_pdf", self.cb.pk)):
            self.assertEqual(self.client.get(reverse(nombre, args=[pk])).status_code, 404, nombre)
        self.assertEqual(self.client.post(reverse("curso_asignatura_quitar", args=[self.acb.pk])).status_code, 404)
        self.assertTrue(AsignaturaCurso.todos.filter(pk=self.acb.pk).exists())
        # el profesor de otro colegio no aparece para asignar
        r = self.client.get(reverse("curso_detalle", args=[self.ca.pk]))
        self.assertNotContains(r, f'value="{self.ub.pk}"')
        # administración: solo usuarios del propio establecimiento
        r = self.client.get("/admin/auth/user/")
        self.assertContains(r, "utp.a")
        self.assertNotContains(r, "utp.b")
        self.assertEqual(self.client.get(reverse("plataforma")).status_code, 403)

    def test_superadministrador(self):
        self.client.force_login(self.sa)
        self.assertRedirects(self.client.get("/cursos/"), reverse("plataforma"), fetch_redirect_response=False)
        r = self.client.get(reverse("plataforma"))
        self.assertContains(r, "Liceo B")
        # crear un establecimiento nuevo con su primera cuenta
        r = self.client.post(reverse("plataforma_nuevo"), {
            "nombre": "Liceo Nuevo", "oferta": "HC", "activo": "on", "modulos": ["curricular"],
            "rol": "DIRECTOR", "nombres": "Ana", "apellidos": "Soto", "usuario": "dir.nuevo", "clave": "clave-segura-1"})
        self.assertRedirects(r, reverse("plataforma"), fetch_redirect_response=False)
        from .models import Establecimiento, OpcionCatalogo
        nuevo = Establecimiento.objects.get(nombre="Liceo Nuevo")
        self.assertEqual(User.objects.get(username="dir.nuevo").perfil.establecimiento, nuevo)
        self.assertTrue(OpcionCatalogo.todos.filter(establecimiento=nuevo, tipo="PROTOCOLO").exists())
        # entrar a un establecimiento y trabajar en él
        self.client.post(reverse("plataforma_entrar", args=[self.b.pk]))
        r = self.client.get(reverse("estudiantes"))
        self.assertContains(r, "Est b")
        self.assertNotContains(r, "Est a")
        # módulo desactivado: sin convivencia
        self.client.force_login(User.objects.get(username="dir.nuevo"))
        self.assertEqual(self.client.get(reverse("convivencia")).status_code, 403)
        # establecimiento desactivado
        nuevo.activo = False
        nuevo.save()
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 403)

    def test_plan_media_tp_y_hc(self):
        from .plan_oficial import aplicar_plan_media, decreto_media
        from .tenencia import en_establecimiento
        with en_establecimiento(self.b):
            nivel = Nivel.objects.create(nombre="III Medio", orden=13, ensenanza="MEDIA")
            tp = Curso.objects.create(nivel=nivel, letra="B", anio=2026, modalidad="TP", especialidad="Administración")
            aplicar_plan_media(tp)
            tipos = set(tp.asignaturas_curso.values_list("asignatura__tipo", flat=True))
            self.assertEqual(tipos, {"ASIGNATURA", "MODULO_TP"})
            self.assertTrue(tp.asignaturas_curso.filter(asignatura__nombre="Filosofía").exists())
            self.assertIn("954", decreto_media(tp))
            hc = Curso.objects.create(nivel=nivel, letra="C", anio=2026, modalidad="HC")
            aplicar_plan_media(hc, ["Física"])
            self.assertTrue(hc.asignaturas_curso.filter(asignatura__tipo="DIFERENCIADA").exists())
        self.client.force_login(self.ub)
        r = self.client.get(reverse("curso_detalle", args=[tp.pk]))
        self.assertContains(r, "Módulos de la especialidad: Administración")
        for nombre in ("acta_final_pdf", "informe_final_pdf"):
            self.assertEqual(self.client.get(reverse(nombre, args=[tp.pk])).status_code, 200)


class LibroDeClasesTests(BaseDatos):
    def setUp(self):
        import datetime

        from .models import Clase
        self.hoy = datetime.date(2026, 4, 6)  # lunes
        self.clase = Clase.objects.create(asignatura_curso=self.mat, fecha=self.hoy, objetivo="OA 1: Sumar fracciones")
        self.est2 = Estudiante.objects.create(rut="9.876.543-3", nombres="Pía", apellido_paterno="Vera", curso=self.curso)

    def test_profesor_planifica_clase_de_evaluacion_y_alimenta_notas(self):
        self.client.force_login(self.profe_mat)
        r = self.client.post(reverse("clase_crear", args=[self.mat.pk]), {
            "fecha": "2026-09-10", "bloques": 2, "objetivo": "OA 5: Resolver problemas", "es_evaluacion": "on",
            "nombre_evaluacion": "Prueba Unidad 3", "ponderacion": "2"})
        self.assertEqual(r.status_code, 302)
        ev = Evaluacion.objects.get(nombre="Prueba Unidad 3")
        self.assertEqual((ev.asignatura_curso, ev.semestre, ev.ponderacion), (self.mat, 2, Decimal("2")))
        self.assertContains(self.client.get(reverse("libro_notas", args=[self.mat.pk])), "Prueba Unidad 3")
        clase = ev.clase
        self.client.post(reverse("clase_editar", args=[clase.pk]), {"fecha": "2026-09-10", "bloques": 2,
                                                                     "objetivo": "OA 5"})
        self.assertFalse(Evaluacion.objects.filter(nombre="Prueba Unidad 3").exists())

    def test_otro_profesor_no_edita_y_jefe_solo_lee(self):
        self.client.force_login(self.profe_len)  # profesor jefe del curso, no de Matemática
        self.assertEqual(self.client.get(reverse("leccionario", args=[self.mat.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("clase_crear", args=[self.mat.pk])).status_code, 403)
        r = self.client.post(reverse("clase_detalle", args=[self.clase.pk]), {"accion": "guardar"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(reverse("libro_curso", args=[self.curso.pk])).status_code, 200)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("libro_curso", args=[self.curso.pk])).status_code, 403)

    def test_asistencia_firma_y_porcentaje_para_informes(self):
        from .models import AsistenciaClase, Clase
        self.client.force_login(self.profe_mat)
        url = reverse("clase_detalle", args=[self.clase.pk])
        r = self.client.post(url, {"accion": "firmar", "clave": "mala", f"a_{self.est.pk}": "A"})
        self.clase.refresh_from_db()
        self.assertFalse(self.clase.firmada)
        self.assertFalse(AsistenciaClase.objects.exists())
        self.client.post(url, {"accion": "firmar", "clave": "clave-segura-123", f"a_{self.est.pk}": "A",
                               f"a_{self.est2.pk}": "T"})
        self.clase.refresh_from_db()
        self.assertTrue(self.clase.firmada)
        self.assertEqual(self.clase.firmada_por, self.profe_mat)
        # segundo día: Ana presente → 50 %; Pía con atraso cuenta como presente → 100 %
        otra = Clase.objects.create(asignatura_curso=self.len, fecha=self.hoy.replace(day=7), objetivo="OA 2")
        self.client.force_login(self.profe_len)
        self.client.post(reverse("clase_detalle", args=[otra.pk]), {"accion": "guardar"})
        self.est.refresh_from_db()
        self.est2.refresh_from_db()
        self.assertEqual((self.est.porcentaje_asistencia, self.est2.porcentaje_asistencia), (Decimal("50.0"), Decimal("100.0")))
        # firmada: ya no se modifica
        self.client.force_login(self.profe_mat)
        self.client.post(url, {"accion": "guardar", f"a_{self.est.pk}": "P"})
        self.assertEqual(AsistenciaClase.objects.get(clase=self.clase, estudiante=self.est).estado, "A")
        self.assertEqual(self.client.get(reverse("clase_editar", args=[self.clase.pk])).status_code, 302)
        # UTP la reabre para corrección
        self.client.force_login(self.utp)
        self.client.post(url, {"accion": "reabrir"})
        self.clase.refresh_from_db()
        self.assertFalse(self.clase.firmada)
        self.assertIn("Reabierta", self.clase.visado_utp)
        # el informe final usa la asistencia del libro
        r = self.client.get(reverse("libro_curso", args=[self.curso.pk]) + "?mes=2026-04")
        self.assertContains(r, "50,0")

    def test_pdfs_y_aislamiento(self):
        from .models import Establecimiento
        from .tenencia import en_establecimiento
        self.client.force_login(self.utp)
        r = self.client.get(reverse("leccionario_pdf", args=[self.mat.pk]))
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        r = self.client.get(reverse("asistencia_mes_pdf", args=[self.curso.pk]) + "?mes=2026-04")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("libro")).status_code, 200)
        otro = Establecimiento.objects.create(nombre="Otro liceo")
        with en_establecimiento(otro):
            from .models import Clase
            self.assertFalse(Clase.objects.filter(pk=self.clase.pk).exists())

    def test_clase_futura_no_registra_asistencia(self):
        from .models import Clase
        futura = Clase.objects.create(asignatura_curso=self.mat, fecha="2099-03-01", objetivo="OA 9")
        self.client.force_login(self.profe_mat)
        self.client.post(reverse("clase_detalle", args=[futura.pk]), {"accion": "guardar"})
        futura.refresh_from_db()
        self.assertFalse(futura.asistencia_registrada)


class AsistentePlanificacionTests(BaseDatos):
    def test_oa_precargados_y_mapeo(self):
        from . import curriculo
        from .models import ObjetivoAprendizaje
        self.assertGreater(ObjetivoAprendizaje.objects.filter(establecimiento__isnull=True).count(), 400)
        self.assertEqual(curriculo.clave_asignatura("Lengua y Literatura"), "lenguaje")
        self.assertEqual(curriculo.clave_asignatura("Educación Física y Salud"), "educacion_fisica")
        self.assertEqual(curriculo.grado_desde_texto("II Medio"), 10)
        oas = curriculo.oas_para(self.mat)  # 5° básico Matemática
        self.assertTrue(oas.filter(numero=22, texto__icontains="áreas").exists())
        self.assertEqual(curriculo.nivel_bloom("Resolver problemas con fracciones"), "aplicar")
        self.assertEqual(curriculo.nivel_bloom("Escribir artículos informativos"), "crear")

    def test_asistente_propone_y_planificacion_guarda_oa(self):
        from . import curriculo
        oa = curriculo.oas_para(self.mat).first()
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("asistente_clase", args=[self.mat.pk]), {"oa": oa.pk, "bloques": 2})
        datos = r.json()
        self.assertIn("Inicio", datos["actividades"])
        self.assertTrue(datos["formativas"] and datos["sumativa"]["rubrica"])
        r = self.client.get(reverse("clase_crear", args=[self.mat.pk]))
        self.assertContains(r, "Asistente de planificación")
        self.client.post(reverse("clase_crear", args=[self.mat.pk]), {
            "fecha": "2026-05-04", "bloques": 2, "unidad": "Unidad 2", "objetivo": datos["objetivo"],
            "actividades": datos["actividades"], "oas": [oa.pk]})
        from .models import Clase
        clase = Clase.objects.get(unidad="Unidad 2")
        self.assertEqual(list(clase.oas.all()), [oa])
        r = self.client.get(reverse("evaluacion_unidad", args=[self.mat.pk]) + "?unidad=Unidad+2")
        self.assertContains(r, "Tabla de especificaciones")
        self.assertContains(r, "100 %")
        # otro profesor no usa el asistente de esta asignatura
        self.client.force_login(self.profe_len)
        self.client.force_login(User.objects.create_user("otro", password="x"))
        self.assertEqual(self.client.get(reverse("asistente_clase", args=[self.mat.pk]), {"oa": oa.pk}).status_code, 403)

    def test_utp_agrega_e_importa_oa_propios_aislados(self):
        from .models import Establecimiento, ObjetivoAprendizaje
        from .tenencia import en_establecimiento
        self.client.force_login(self.utp)
        self.client.post(reverse("curriculum"), {"asignatura": "otra", "grado": 5, "numero": 1,
                                                 "texto": "Cultivar un huerto escolar"})
        archivo = xlsx([["Asignatura", "Nivel", "OA", "Texto"], ["Inglés", "5° básico", 3, "Leer textos breves"]])
        self.client.post(reverse("curriculum"), {"archivo": archivo})
        propios = ObjetivoAprendizaje.objects.filter(establecimiento__isnull=False)
        self.assertEqual(sorted(propios.values_list("asignatura", flat=True)), ["ingles", "otra"])
        otro = Establecimiento.objects.create(nombre="Otro")
        with en_establecimiento(otro):
            self.assertFalse(ObjetivoAprendizaje.disponibles().filter(texto__icontains="huerto").exists())
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.post(reverse("curriculum"), {"asignatura": "otra", "grado": 5, "numero": 2,
                                                                  "texto": "x"}).status_code, 403)


class AlertasTests(BaseDatos):
    def test_alertas_visibles_por_rol_y_contenido(self):
        Perfil.objects.create(usuario=User.objects.create_user("insp", password="x"), rol=Perfil.Rol.INSPECTOR)
        Perfil.objects.create(usuario=User.objects.create_user("conv", password="x"), rol=Perfil.Rol.CONVIVENCIA)
        Calificacion.objects.filter(estudiante=self.est).update(nota=Decimal("3.2"))
        Estudiante.objects.filter(pk=self.est.pk).update(porcentaje_asistencia=Decimal("80"))
        from django.utils import timezone
        self.curso.anio = timezone.localdate().year
        self.curso.save()
        for u in ("director", "utp", "insp", "conv"):
            self.client.force_login(User.objects.get(username=u))
            self.assertContains(self.client.get(reverse("alertas") + "?ver=rendimiento"), "Pérez")
            self.assertContains(self.client.get(reverse("alertas") + "?ver=asistencia"), "Bajo 85")
        self.client.force_login(self.profe_mat)  # profesor de asignatura sin jefatura
        self.assertEqual(self.client.get(reverse("alertas")).status_code, 403)
        self.client.force_login(self.profe_len)  # profesor jefe: ve su curso
        r = self.client.get(reverse("alertas") + "?ver=notas")
        self.assertEqual(r.status_code, 200)

    def test_nivelacion_muestra_oa_de_niveles_anteriores(self):
        from . import curriculo
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("clase_crear", args=[self.mat.pk]))
        self.assertContains(r, "Nivelación")
        anterior = curriculo.oas_para(self.mat, anteriores=True).filter(grado=4).first()
        self.assertEqual(self.client.get(reverse("asistente_clase", args=[self.mat.pk]), {"oa": anterior.pk}).status_code, 200)


class ResultadosTests(BaseDatos):
    def test_gestion_registra_simce_y_profesor_no_entra(self):
        from .models import ResultadoSimce
        self.client.force_login(User.objects.get(username="utp"))
        self.assertEqual(self.client.get(reverse("resultados")).status_code, 200)
        datos = {"s-anio": 2024, "s-nivel": "4B", "s-prueba": "LEC", "s-puntaje": 265, "s-puntaje_nacional": 262,
                 "guardar_simce": "1"}
        self.client.post(reverse("resultados") + "?ver=simce", datos)
        datos["s-puntaje"] = 270  # mismo año, nivel y prueba: actualiza
        self.client.post(reverse("resultados") + "?ver=simce", datos)
        self.assertEqual(ResultadoSimce.objects.count(), 1)
        self.assertEqual(ResultadoSimce.objects.get().puntaje, 270)
        self.assertContains(self.client.get(reverse("resultados") + "?ver=simce"), "<svg")
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("resultados")).status_code, 403)


class NivelesSostenedorTests(VariosEstablecimientosTests):
    """Superadministrador › sostenedor (con su administrador) › establecimiento; un colegio solo tiene su admin."""

    def setUp(self):
        from .models import Establecimiento, Sostenedor
        self.sost = Sostenedor.objects.create(nombre="Corporación X")
        Establecimiento.objects.filter(pk=self.b.pk).update(sostenedor=self.sost)
        self.c = Establecimiento.objects.create(nombre="Liceo C", sostenedor=self.sost)
        self.adm = User.objects.create_user("adm.red", password="x")
        Perfil.objects.create(usuario=self.adm, rol="ADMIN_SOSTENEDOR", sostenedor=self.sost)

    def test_admin_sostenedor_elige_entre_sus_establecimientos(self):
        self.assertIsNone(Perfil.objects.get(usuario=self.adm).establecimiento)
        self.client.force_login(self.adm)
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("red"))
        r = self.client.get(reverse("red"))
        self.assertContains(r, "Liceo B")
        self.assertContains(r, "Liceo C")
        self.assertNotContains(r, self.a.nombre)
        self.assertEqual(self.client.post(reverse("red_entrar", args=[self.a.pk])).status_code, 404)
        self.client.post(reverse("red_entrar", args=[self.b.pk]))
        r = self.client.get(reverse("estudiantes"))
        self.assertContains(r, "Est b")
        self.assertNotContains(r, "Est a")
        self.assertEqual(self.client.get(reverse("libro_notas", args=[self.acb.pk])).status_code, 200)
        # crea el administrador de plataforma de un establecimiento
        self.client.post(reverse("red"), {"destino": str(self.c.pk), "rol": "ADMIN", "nombres": "A", "apellidos": "B",
                                          "usuario": "adm.c", "clave": "clave12345"})
        p = Perfil.objects.get(usuario__username="adm.c")
        self.assertEqual((p.establecimiento, p.sostenedor, p.es_gestion), (self.c, None, True))
        r = self.client.post(reverse("red"), {"destino": "", "rol": "PROFESOR", "nombres": "A", "apellidos": "B",
                                              "usuario": "malo", "clave": "clave12345"})
        self.assertContains(r, "trabajan en todos")

    def test_sostenedor_solo_consulta_y_otros_no_entran(self):
        u = User.objects.create_user("sost.red", password="x")
        Perfil.objects.create(usuario=u, rol="SOSTENEDOR", sostenedor=self.sost)
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("red")).status_code, 200)
        self.assertEqual(self.client.post(reverse("red"), {"rol": "ADMIN"}).status_code, 403)
        self.client.force_login(self.ua)
        self.assertEqual(self.client.get(reverse("red")).status_code, 403)

    def test_superadmin_crea_sostenedor_con_su_administrador(self):
        from .models import Establecimiento, Sostenedor
        self.client.force_login(self.sa)
        self.client.post(reverse("sostenedor_nuevo"), {
            "nombre": "Fundación Y", "rut": "", "activo": "on", "establecimientos": [self.a.pk],
            "rol": "ADMIN_SOSTENEDOR", "nombres": "N", "apellidos": "M", "usuario": "adm.y", "clave": "clave12345"})
        y = Sostenedor.objects.get(nombre="Fundación Y")
        self.assertEqual(Establecimiento.objects.get(pk=self.a.pk).sostenedor, y)
        self.assertEqual(Perfil.objects.get(usuario__username="adm.y").sostenedor, y)
        self.assertContains(self.client.get(reverse("plataforma")), "Fundación Y")


class GestionPersonalTests(BaseDatos):
    def test_calculo_de_asignaciones(self):
        from .models import Establecimiento, Funcionario, ParametrosPersonal
        from .personal import asignaciones
        est = Establecimiento.actual()
        p = ParametrosPersonal(brp_titulo=100000, brp_mencion=40000, por_bienio=10000, tramo_avanzado=200000,
                               prioritarios_fijo=40000, prioritarios_80=60000)
        f = Funcionario(cargo="DOCENTE", titulo="Profesor", brp_mencion=True, horas_contrato=Decimal("22"),
                        tramo="AVANZADO", anios_experiencia=9)
        est.pct_prioritarios = Decimal("85")
        m = asignaciones(f, est, p)
        self.assertEqual(m["brp"], 70000)                     # (100.000 + 40.000) × 22/44
        self.assertEqual(m["tramo"], 120000)                  # (200.000 + 4 bienios × 10.000) × 1/2
        self.assertEqual(m["prioritarios"], 24000 + 20000 + 30000)  # 20 % tramo + fijo + adicional 80 %
        est.pct_prioritarios = Decimal("50")
        self.assertEqual(asignaciones(f, est, p)["prioritarios"], 0)
        est.rural = True
        self.assertEqual(asignaciones(f, est, p)["prioritarios"], 12000)  # rural 45-59 %: 10 % del tramo
        f.cargo = "ASISTENTE"
        self.assertEqual(asignaciones(f, est, p)["total"], 0)

    def test_pagina_y_permisos(self):
        from .models import Funcionario, ParametrosPersonal
        Funcionario.objects.create(rut="11.111.111-1", nombres="Ana", apellido_paterno="Soto", horas_contrato=44,
                                   titulo="Profesora", tramo="TEMPRANO", evaluacion_docente="BASICO")
        self.client.force_login(User.objects.get(username="director"))
        r = self.client.get(reverse("personal"))
        self.assertContains(r, "Ana Soto")
        self.assertContains(r, "plan de superación")
        self.client.post(reverse("personal"), {"guardar_parametros": "1", "brp_titulo": 90000, "brp_mencion": 0,
                         "por_bienio": 0, "tramo_inicial": 0, "tramo_temprano": 80000, "tramo_avanzado": 0,
                         "tramo_experto_i": 0, "tramo_experto_ii": 0, "prioritarios_fijo": 0, "prioritarios_80": 0})
        self.assertEqual(ParametrosPersonal.objects.get().brp_titulo, 90000)
        self.assertContains(self.client.get(reverse("personal")), "$170.000")
        self.assertEqual(self.client.get(reverse("personal") + "?exportar=excel").status_code, 200)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("personal")).status_code, 403)


class HorariosTests(BaseDatos):
    def setUp(self):
        from .models import anio_actual
        Curso.objects.filter(pk__in=[self.curso.pk, self.otro_curso.pk]).update(anio=anio_actual())
        AsignaturaCurso.objects.filter(pk=self.mat.pk).update(horas_semanales=Decimal("6"))
        AsignaturaCurso.objects.filter(pk=self.len.pk).update(horas_semanales=Decimal("7.5"))
        # el mismo profesor de matemática dicta en el otro curso
        AsignaturaCurso.objects.create(curso=self.otro_curso, asignatura=self.mat.asignatura, profesor=self.profe_mat,
                                       horas_semanales=Decimal("6"))

    def test_genera_sin_topes_y_respeta_lo_fijado(self):
        from .models import BloqueHorario, HorarioClase
        self.client.force_login(self.utp)
        self.client.get(reverse("horarios"))  # crea la jornada sugerida
        b1 = BloqueHorario.objects.get(numero=1)
        self.client.post(reverse("horarios"), {"accion": "celda", "curso": self.curso.pk, "dia": 1, "bloque": b1.pk,
                                               "ac": self.len.pk})
        self.client.post(reverse("horarios"), {"accion": "generar", "curso": "todos"})
        self.assertEqual(HorarioClase.objects.filter(asignatura_curso=self.mat).count(), 6)
        self.assertEqual(HorarioClase.objects.filter(asignatura_curso=self.len).count(), 8)  # 7,5 h -> 8 bloques
        self.assertTrue(HorarioClase.objects.filter(curso=self.curso, dia=1, bloque=b1, fijo=True,
                                                    asignatura_curso=self.len).exists())
        slots = list(HorarioClase.objects.filter(asignatura_curso__profesor=self.profe_mat).values_list("dia", "bloque"))
        self.assertEqual(len(slots), len(set(slots)))  # sin topes del profesor
        # a mano: no permite poner al profesor en dos cursos a la vez
        h = HorarioClase.objects.filter(asignatura_curso=self.mat).first()
        otro = AsignaturaCurso.objects.get(curso=self.otro_curso)
        HorarioClase.objects.filter(curso=self.otro_curso, dia=h.dia, bloque=h.bloque).delete()
        r = self.client.post(reverse("horarios"), {"accion": "celda", "curso": self.otro_curso.pk, "dia": h.dia,
                                                   "bloque": h.bloque_id, "ac": otro.pk}, follow=True)
        self.assertContains(r, "ya tiene clase")

    def test_profesor_ve_su_horario_y_no_edita(self):
        from .horarios import generar
        generar(Curso.objects.filter(pk__in=[self.curso.pk, self.otro_curso.pk]), semilla=1)
        self.client.force_login(self.profe_mat)
        r = self.client.get(reverse("horarios"))
        self.assertContains(r, "Matemática")
        self.assertNotContains(r, "Generar horario")
        self.assertEqual(self.client.post(reverse("horarios"), {"accion": "generar", "curso": "todos"}).status_code, 403)


class AsistenciaDiariaHoraTests(BaseDatos):
    def test_toma_la_clase_de_las_diez(self):
        import datetime
        from .libro import asistencia_diaria
        from .models import AsistenciaClase, Clase
        dia = datetime.date(2026, 4, 6)
        temprano = Clase.objects.create(asignatura_curso=self.mat, fecha=dia, hora_inicio=datetime.time(8, 0),
                                        bloques=2, objetivo="x", asistencia_registrada=True)
        diez = Clase.objects.create(asignatura_curso=self.len, fecha=dia, hora_inicio=datetime.time(9, 45),
                                    bloques=2, objetivo="y", asistencia_registrada=True)
        AsistenciaClase.objects.create(clase=temprano, estudiante=self.est, estado="A")  # llegó tarde al colegio
        AsistenciaClase.objects.create(clase=diez, estudiante=self.est, estado="P")
        self.assertEqual(asistencia_diaria(self.curso)[(self.est.pk, dia)], "P")


class OATalleresTests(BaseDatos):
    def test_oa_propios_de_un_taller(self):
        from . import curriculo
        from .models import ObjetivoAprendizaje
        taller = Asignatura.objects.create(nombre="Taller de Robótica", tipo="TALLER")
        ac = AsignaturaCurso.objects.create(curso=self.curso, asignatura=taller, profesor=self.profe_mat)
        self.client.force_login(self.utp)
        self.client.post(reverse("curriculum"), {"asignatura_propia": taller.pk, "grado": 0, "numero": 1,
                                                 "texto": "Programar un robot simple con secuencias."})
        oa = ObjetivoAprendizaje.objects.get(asignatura_propia=taller)
        self.assertEqual(oa.asignatura, "otra")
        self.assertIn(oa, curriculo.oas_para(ac))
        self.assertNotIn(oa, curriculo.oas_para(self.mat))
        r = self.client.get(reverse("curriculum") + f"?asignatura=p{taller.pk}")
        self.assertContains(r, "Programar un robot")
        self.client.force_login(self.profe_mat)
        self.assertContains(self.client.get(reverse("clase_crear", args=[ac.pk])), "Programar un robot")


class ConceptosBasicaTests(BaseDatos):
    def test_ingreso_y_vista_con_conceptos(self):
        from .models import Establecimiento
        est = Establecimiento.actual()
        nivel = Nivel.objects.create(nombre="2° Básico", orden=2)
        curso = Curso.objects.create(nivel=nivel, letra="A", anio=2026)
        ac = AsignaturaCurso.objects.create(curso=curso, asignatura=self.mat.asignatura, profesor=self.profe_mat)
        alumno = Estudiante.objects.create(rut="15.555.555-8", nombres="Sofía", apellido_paterno="Rojas", curso=curso)
        ev = Evaluacion.objects.create(asignatura_curso=ac, nombre="Prueba", semestre=1)
        self.client.force_login(self.profe_mat)
        campo = f"n_{alumno.pk}_{ev.pk}"
        r = self.client.post(reverse("libro_notas", args=[ac.pk]), {campo: "MB"}, follow=True)
        self.assertContains(r, "no es una nota")  # sin la opción, «MB» no se acepta
        Establecimiento.objects.filter(pk=est.pk).update(conceptos_basica=True)
        self.client.post(reverse("libro_notas", args=[ac.pk]), {campo: "mb"})
        self.assertEqual(Calificacion.objects.get(evaluacion=ev).nota, Decimal("6.5"))
        r = self.client.get(reverse("libro_notas", args=[ac.pk]))
        self.assertContains(r, 'value="MB"')
        # 5° básico sigue con notas
        self.assertNotContains(self.client.get(reverse("libro_notas", args=[self.mat.pk])), "se evalúa con conceptos")


class ModulosAdministrativosTests(BaseDatos):
    def setUp(self):
        from .models import Funcionario
        self.f = Funcionario.objects.create(rut="11.111.111-1", nombres="Ana", apellido_paterno="Soto",
                                            horas_contrato=44)
        self.insp = User.objects.create_user("insp", password="x")
        Perfil.objects.create(usuario=self.insp, rol=Perfil.Rol.INSPECTOR)

    def test_asistencia_del_personal(self):
        from .models import AsistenciaFuncionario
        self.client.force_login(self.insp)
        url = reverse("asistencia_personal") + "?fecha=2026-05-04"
        self.client.post(url, {f"estado_{self.f.pk}": "T", f"atraso_{self.f.pk}": "15", f"entrada_{self.f.pk}": "08:15"})
        a = AsistenciaFuncionario.objects.get(funcionario=self.f)
        self.assertEqual((a.estado, a.minutos_atraso, a.fecha.isoformat()), ("T", 15, "2026-05-04"))
        r = self.client.get(reverse("asistencia_personal_mes") + "?mes=2026-05")
        self.assertContains(r, "Ana Soto")
        self.assertEqual(self.client.get(reverse("asistencia_personal_mes") + "?mes=2026-05&exportar=excel").status_code, 200)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("asistencia_personal")).status_code, 403)

    def test_pme_acciones_y_gastos(self):
        from .models import AccionPME, GastoSEP
        self.client.force_login(self.utp)
        self.client.get(reverse("pme") + "?anio=2026")
        self.client.post(reverse("pme_accion_nueva") + "?anio=2026", {
            "dimension": "PEDAGOGICA", "nombre": "Reforzamiento", "monto_sep": 1000000, "estado": "EJECUTADA",
            "avance": 20})
        accion = AccionPME.objects.get()
        self.assertEqual(accion.avance, 100)
        self.client.post(reverse("pme_gastos") + "?anio=2026", {"fecha": "2026-05-04", "accion": accion.pk,
                         "categoria": "RECURSOS", "detalle": "Textos", "monto": 250000})
        self.assertEqual(GastoSEP.objects.get().monto, 250000)
        r = self.client.get(reverse("pme") + "?anio=2026")
        self.assertContains(r, "Reforzamiento")
        self.assertContains(r, "$250.000")
        self.assertEqual(self.client.get(reverse("pme_gastos") + "?anio=2026&exportar=excel").status_code, 200)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("pme")).status_code, 403)


class DotacionTests(BaseDatos):
    def test_dotacion_vs_plan(self):
        from .models import Funcionario, anio_actual
        from .personal import dotacion
        Curso.objects.filter(pk=self.curso.pk).update(anio=anio_actual())
        AsignaturaCurso.objects.filter(pk=self.mat.pk).update(horas_semanales=Decimal("40"))
        AsignaturaCurso.objects.filter(pk=self.len.pk).update(horas_semanales=Decimal("6"))
        Funcionario.objects.create(rut="11.111.111-1", nombres="Mate", apellido_paterno="A", horas_contrato=44,
                                   usuario=self.profe_mat)
        Funcionario.objects.create(rut="22.222.222-2", nombres="Sin", apellido_paterno="Carga", horas_contrato=30)
        from .models import Establecimiento
        d = dotacion(Establecimiento.actual(), anio_actual())
        self.assertEqual(d["horas_plan"], Decimal("46"))
        estados = {x["f"].nombres: x["estado"] for x in d["filas"]}
        self.assertEqual(estados, {"Mate": "sobrecarga", "Sin": "sin_carga"})  # 40 h > 38,1 lectivas
        self.assertEqual([u for u, _ in d["sin_ficha"]], [self.profe_len])
        self.client.force_login(self.utp)
        r = self.client.get(reverse("dotacion"))
        self.assertContains(r, "Sobrecargado")
        self.client.post(reverse("personal_nuevo"), {"establecimiento_destino": Establecimiento.actual().pk,
                         "rut": "33.333.333-3", "nombres": "Nueva", "apellido_paterno": "Docente", "cargo": "DOCENTE",
                         "tipo_contrato": "TITULAR", "horas_contrato": 30, "activo": "on"})
        self.assertTrue(Funcionario.objects.filter(nombres="Nueva").exists())


class HorarioImprimibleTests(HorariosTests):
    def test_pdf_una_hoja_por_curso(self):
        import re

        from .horarios import generar

        def paginas(contenido):
            return len(re.findall(rb"/Type\s*/Page[^s]", contenido))

        generar(Curso.objects.filter(pk__in=[self.curso.pk, self.otro_curso.pk]), semilla=1)
        self.client.force_login(self.utp)
        r = self.client.get(reverse("horarios_pdf") + f"?curso={self.curso.pk}")
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(paginas(r.content), 1)
        r = self.client.get(reverse("horarios_pdf") + "?todos=cursos")
        self.assertEqual(paginas(r.content), 2)
        self.client.force_login(self.profe_mat)
        self.assertEqual(self.client.get(reverse("horarios_pdf") + f"?profesor={self.profe_mat.pk}").status_code, 200)
        self.assertEqual(self.client.get(reverse("horarios_pdf") + "?todos=cursos").status_code, 403)
