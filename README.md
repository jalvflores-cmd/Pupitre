# Pupitre

Aplicación web de gestión curricular para administrar cursos, asignaturas, estudiantes, calificaciones y convivencia escolar
de un establecimiento educacional chileno, con carga desde Excel y emisión de informes en PDF y Excel.

## Funcionalidades

| Área | Qué permite |
|---|---|
| **Cursos y niveles** | Niveles (1° Básico … IV Medio), cursos por año con letra y profesor(a) jefe. |
| **Asignaturas y carga académica** | Asignaturas del establecimiento y qué profesor(a) dicta cada asignatura en cada curso. |
| **Estudiantes** | RUT (validado con dígito verificador), nombres, fecha de nacimiento, dirección, comuna, teléfono, email, apoderado(a), contacto y teléfono de emergencia, estado activo/retirado. |
| **Calificaciones** | Libro de notas por asignatura: evaluaciones por semestre con ponderación, ingreso tipo planilla (escala 1,0 – 7,0; notas bajo 4,0 en rojo), promedios semestrales y final automáticos. |
| **Funcionarios** | Ficha de docentes y asistentes: título, mención, tipo de contrato (titular/contrata), horas de contrato y distribución lectiva/no lectiva según la Ley 20.903 (65/35, o 60/40 para docentes de pre-kínder a 4° básico con 80 % o más de alumnos prioritarios; se puede fijar a mano). |
| **Asignaturas y talleres JEC** | Asignaturas del plan oficial con horas semanales por curso. Religión Católica y Religión Evangélica se califican con nota; cada estudiante cursa la de su credo (o ninguna si no opta) y, según el Decreto 67/2018, no inciden en el promedio ni en la promoción. Orientación se informa con concepto (MB, B, S, I). Los talleres JEC son parte de la carga académica de cada curso: en la página del curso, UTP y Dirección agregan asignaturas o talleres, asignan profesor(a) y horas semanales. Los talleres se califican con nota que cuenta para el promedio (configurable por taller). |
| **Convivencia** | Anotaciones positivas, negativas u observaciones, con gravedad (leve/grave/gravísima), asignatura, descripción y medida tomada. |
| **Derivaciones, protocolos, redes y entrevistas** | Las faltas graves y gravísimas se derivan automáticamente a Convivencia Escolar (las demás, si quien anota lo marca). Convivencia registra el estado de la derivación, el protocolo activado (vulneración de derechos, maltrato, connotación sexual, drogas, autolesión, Aula Segura, etc.) y el seguimiento. Cada estudiante tiene un registro de redes externas (Mejor Niñez, OLN, OPD, Tribunal de Familia, CESFAM, etc.) y de entrevistas (apoderado/a, estudiante o activación de protocolo), con PDF para firmar y un formato en blanco para completar a mano. **Datos confidenciales:** solo los ven Dirección, UTP, Inspectoría, Convivencia y el profesor(a) jefe del curso; el sostenedor y los profesores de asignatura solo ven que la anotación fue derivada. |
| **Carga de datos** | Acepta Excel (.xlsx/.xls), CSV, Word (.docx, primera tabla) y la **nómina de estudiantes descargada desde SIGE tal como viene** (se reconoce sola: RUN/IPE, curso, género, contacto, asistencia, fechas de incorporación y retiro, código de etnia; valida que el RBD sea el del establecimiento). El profesor(a) jefe puede subir la nómina SIGE de su curso. |
| **Carga desde Excel** | Plantillas descargables para estudiantes, notas (por asignatura y curso) y anotaciones. Cada importación es *todo o nada*: si hay errores se informa fila por fila y no se guarda nada. |
| **Informes** | En formato oficial (membrete República de Chile / Ministerio de Educación, RBD, Decreto 67/2018): Informe de Calificaciones (PDF), Certificado Anual de Estudios con notas en palabras y asistencia (PDF), Acta de Calificaciones Finales y Promoción Escolar con resumen por sexo (PDF horizontal), informe final del curso (Excel), notas por asignatura (Excel), listados de estudiantes y anotaciones (Excel). |

### Reglas de cálculo

- Promedio semestral = promedio ponderado de las evaluaciones del semestre (la ponderación es un peso relativo: 1 = todas iguales, o porcentajes).
- Promedio final de la asignatura = promedio de los semestres con notas.
- Promedio general = promedio de los promedios finales de las asignaturas.
- Redondeo a un decimal (0,05 sube: 3,95 → 4,0).
- Situación final según Decreto 67/2018: promovido si aprueba todo; o 1 reprobada con promedio ≥ 4,5; o 2 reprobadas con promedio ≥ 5,0. **La asistencia (85 %) no se registra en la plataforma y debe verificarse aparte.**

## Roles y acceso

| Rol | Acceso |
|---|---|
| **Sostenedor(a)** | Ve todo (cursos, notas, estudiantes, convivencia e informes) en modo solo lectura. |
| **Director(a)** y **Jefe(a) de UTP** | Todo: todos los niveles, cursos, asignaturas y estudiantes. Editan notas y estudiantes, importan, emiten informes, entran a **Configuración** y aprueban las **Solicitudes** de modificación de datos. |
| **Inspector(a) general** y **Encargado(a) de convivencia** | Ven todos los cursos y notas (sin editarlas). Registran, importan y eliminan anotaciones en cualquier curso, actualizan directamente los datos de contacto (dirección, teléfonos, apoderado) y solicitan cambios de nombre, RUT o fecha de nacimiento. |
| **Profesor(a)** | Solo las asignaturas que dicta: ve y edita sus notas, ve a los estudiantes de esos cursos y registra anotaciones. |
| **Profesor(a) jefe** | Además, consulta (sin editar) todas las notas de su curso y emite los informes de su curso. Puede **solicitar** cambios en el nombre y los datos de sus estudiantes; los cambios se aplican solo cuando Jefe(a) de UTP o Dirección los aprueba. |

Todos los usuarios tienen el botón **Enviar comentarios**; Dirección y UTP los revisan en *menú de usuario › Ver comentarios recibidos* (exportables a Excel).

## Publicar en internet (versión de prueba en Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jalvflores-cmd/Pupitre)

El archivo `render.yaml` crea el sitio web y su base de datos PostgreSQL en el plan gratuito de Render,
con datos ficticios y usuarios de prueba (`MODO_DEMO=true`, contraseña `demo1234`):
`sostenedor`, `director`, `utp`, `inspector`, `convivencia`, `profe.historia`, `profe.lenguaje`, `profe.matematica`, `profe.ciencias`.

Limitaciones del plan gratuito: el sitio "se duerme" tras 15 minutos sin uso (la primera visita después tarda
cerca de un minuto) y la base de datos gratuita vence a los 30 días. Para uso real con datos de estudiantes,
cambie a un plan pagado, ponga `MODO_DEMO=false` y cree los usuarios reales.

## Puesta en marcha

### Opción A: Docker (recomendada para producción)

```bash
# 1. Edite docker-compose.yml: cambie las claves y ALLOWED_HOSTS (dominio o IP del servidor)
docker compose up -d
# 2. Cree el primer usuario (será administrador con acceso total)
docker compose exec web python manage.py createsuperuser
```

Abra `http://<servidor>:8000`. Para usar HTTPS, ponga la aplicación detrás de un proxy (Nginx, Caddy o el
del proveedor de hosting) y deje `COOKIES_SEGURAS=true`.

También funciona en servicios como Render, Railway o Fly.io: use el `Dockerfile`, una base PostgreSQL
del proveedor y las variables de entorno de abajo.

### Opción B: local (para probar)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py datos_demo          # opcional: datos de ejemplo
python manage.py runserver
```

Usuarios de demostración (contraseña `demo1234`): `sostenedor`, `director`, `utp`, `inspector`, `convivencia`, `profe.historia`, `profe.lenguaje`, `profe.matematica`, `profe.ciencias`.

### Variables de entorno

| Variable | Descripción | Por defecto |
|---|---|---|
| `SECRET_KEY` | Clave secreta larga y aleatoria (obligatoria en producción) | solo desarrollo |
| `DEBUG` | `true` solo en desarrollo | `true` (el Dockerfile la pone en `false`) |
| `DATABASE_URL` | Ej.: `postgres://usuario:clave@host:5432/bd` | SQLite local |
| `ALLOWED_HOSTS` | Dominios/IP separados por coma | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Ej.: `https://notas.micolegio.cl` | vacío |
| `COOKIES_SEGURAS` | `false` si aún no hay HTTPS | `true` |
| `MODO_DEMO` | `true` carga datos ficticios y muestra los usuarios de prueba al ingresar | `false` |

## Primeros pasos después de instalar

1. **Configuración › Establecimiento**: nombre, RBD, dirección, director(a) y jefe(a) de UTP (aparecen en los informes).
2. **Configuración › Usuarios**: cree a cada funcionario y asigne su rol (Director, UTP o Profesor).
3. **Configuración › Asignaturas** y **Niveles**.
4. **Importar Excel › Estudiantes**: la planilla crea automáticamente los cursos que falten.
5. **Configuración › Cursos**: asigne profesor(a) jefe y, en la misma pantalla, la carga académica (asignatura + profesor).
6. Los profesores ingresan notas en su **libro de notas** (dato a dato) o subiendo la plantilla Excel.

## Respaldo

Con PostgreSQL: `docker compose exec db pg_dump -U curricular curricular > respaldo.sql`.
Programe este comando a diario (cron) y guarde los respaldos fuera del servidor.

## Desarrollo

- Stack: Python 3.12+, Django 5.2, openpyxl (Excel), ReportLab (PDF), Bootstrap 5 (incluido localmente, no depende de internet).
- Pruebas: `python manage.py test academico`
- Estructura principal: `academico/models.py` (datos), `permisos.py` (reglas de acceso), `calculos.py` (promedios),
  `importacion.py` / `exportacion.py` (Excel y PDF), `views.py`, `templates/`.


## Instalación local en un establecimiento (Windows)

Para que una escuela use Pupitre en su propio computador, solo dentro de su red y con respaldos propios,
siga la guía [docs/Guia_instalacion_Pupitre.pdf](docs/Guia_instalacion_Pupitre.pdf). En resumen:

1. Extraer el proyecto en `C:\Pupitre` y ejecutar `windows\instalar.bat` (instala Python si falta, prepara todo,
   deja Pupitre arrancando con el equipo y abre el puerto 8000 en la red interna).
2. Completar el asistente de bienvenida (datos de la escuela y la primera cuenta de Dirección/UTP).
3. Los demás computadores entran a `http://NOMBRE-DEL-EQUIPO:8000`.

Respaldos: automáticos cada día en `C:\Pupitre\respaldos` (menú **Respaldos**), con copia opcional a un disco externo
y a Google Drive para escritorio (sincronizando esa carpeta). Restaurar con `windows\restaurar.bat`;
actualizar con `windows\actualizar.bat`.

## Configuración editable

Menú **Configuración** (Dirección y UTP): datos del establecimiento, logo institucional (menú, ingreso, planillas
Excel y entrevistas; no en los documentos oficiales Mineduc), color institucional, texto al pie de documentos
internos, y las listas de protocolos de convivencia y redes de apoyo externas.


## Plataforma con varios establecimientos

Pupitre puede alojar varios establecimientos en un mismo servidor. Cada uno tiene sus propios usuarios, cursos,
estudiantes, notas, logo, color y listas, y **nadie ve datos de otro establecimiento** (el filtro se aplica en
todas las consultas: ver `academico/tenencia.py` y `academico/middleware.py`).

- **Superadministrador(a)** (`/plataforma/`): crea y edita establecimientos, los activa o desactiva, elige sus
  módulos (gestión curricular, convivencia, funcionarios; próximamente módulos de gestión administrativa) y puede
  «entrar» a cualquiera para dar soporte.
- **Enseñanza Media**: 1° y 2° medio (Decreto 1264/2016); 3° y 4° medio con formación general (Decreto 193/2019)
  más plan diferenciado Científico-Humanista (electivos) o módulos de la especialidad Técnico-Profesional.
  Cada curso indica su modalidad (HC/TP), especialidad, mención y decreto del plan.
- Demostración: Escuela Gabriela Mistral (básica), Liceo Los Coigües (HC), Liceo Industrial y Comercial
  Las Araucarias (TP: Administración y Mecánica Automotriz) y Liceo Polivalente Río Ñuble (HC + TP Gastronomía).
  Usuarios: `superadmin`, `director.hc`, `utp.tp`, `profe.poli`, etc. (contraseña `demo1234`).

La instalación local (Windows) sigue funcionando con un solo establecimiento, sin cambios.
