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
| **Convivencia** | Anotaciones positivas, negativas u observaciones, con gravedad (leve/grave/gravísima), asignatura, descripción y medida tomada. |
| **Carga desde Excel** | Plantillas descargables para estudiantes, notas (por asignatura y curso) y anotaciones. Cada importación es *todo o nada*: si hay errores se informa fila por fila y no se guarda nada. |
| **Informes** | Informe de notas por estudiante (PDF), informe final con situación de promoción (PDF), acta de calificaciones finales del curso (PDF horizontal), informe final del curso (Excel), notas por asignatura (Excel), listados de estudiantes y anotaciones (Excel). |

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
