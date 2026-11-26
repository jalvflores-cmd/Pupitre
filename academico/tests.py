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
        self.assertEqual(situacion_final(Decimal("4.4"), uno), "No promovido(a)")
        self.assertEqual(situacion_final(Decimal("5.0"), uno * 2), "Promovido(a)")
        self.assertEqual(situacion_final(Decimal("6.0"), uno * 3), "No promovido(a)")


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
