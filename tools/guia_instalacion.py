"""Genera docs/Guia_instalacion_Pupitre.pdf (guía paso a paso para instalar Pupitre en una escuela)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

AZUL = colors.HexColor("#1F3A5F")
SUAVE = colors.HexColor("#EEF3F9")
AMARILLO = colors.HexColor("#FFF6DB")
base = getSampleStyleSheet()
N = ParagraphStyle("n", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=5)
H1 = ParagraphStyle("h1", parent=N, fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=AZUL,
                    spaceBefore=14, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=N, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=AZUL,
                    spaceBefore=8, spaceAfter=4)
TIT = ParagraphStyle("t", parent=N, fontName="Helvetica-Bold", fontSize=26, leading=32, textColor=AZUL,
                     alignment=TA_CENTER)
SUB = ParagraphStyle("s", parent=N, fontSize=13, leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#4A5568"))
MONO = ParagraphStyle("m", parent=N, fontName="Courier-Bold", fontSize=11, leading=15)


def p(t):
    return Paragraph(t, N)


def pasos(items):
    return ListFlowable([ListItem(Paragraph(t, N), leftIndent=14) for t in items], bulletType="1",
                        bulletFontName="Helvetica-Bold", bulletColor=AZUL, leftIndent=16)


def vinetas(items):
    return ListFlowable([ListItem(Paragraph(t, N), leftIndent=12) for t in items], bulletType="bullet",
                        start="•", leftIndent=14)


def caja(texto, fondo=SUAVE, titulo=None):
    contenido = ([Paragraph(f"<b>{titulo}</b>", N)] if titulo else []) + [Paragraph(texto, N)]
    t = Table([[contenido]], colWidths=[16.5 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo), ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 8)])


def tabla(filas, anchos):
    t = Table([[Paragraph(str(c), N) for c in f] for f in filas], colWidths=anchos)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), SUAVE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


h = []
h += [Spacer(1, 4 * cm), Paragraph("Pupitre", TIT), Spacer(1, 6),
      Paragraph("Guía de instalación en el computador del establecimiento", SUB), Spacer(1, 1.2 * cm),
      caja("Pupitre queda instalado en <b>un computador de la escuela</b> (el «servidor»). Los demás computadores "
           "de la escuela lo abren en el navegador, sin instalar nada. <b>La información no sale del establecimiento</b>: "
           "se guarda en ese computador, con respaldos diarios automáticos y, si lo desean, una copia en Google Drive."),
      Spacer(1, 1 * cm),
      tabla([["Sección", "Página aprox."], ["1. Qué se necesita", "2"], ["2. Instalar Pupitre", "2"],
             ["3. Primera configuración", "3"], ["4. Entrar desde los otros computadores", "4"],
             ["5. Respaldos y Google Drive", "5"], ["6. Restaurar un respaldo", "6"],
             ["7. Actualizar a una versión nueva", "6"], ["8. Problemas frecuentes", "7"],
             ["9. Cuidado de los datos personales", "7"]], [12 * cm, 4.5 * cm]),
      PageBreak()]

h += [Paragraph("1. Qué se necesita", H1),
      tabla([["Elemento", "Recomendado"],
             ["Computador servidor", "Windows 10 u 11 · 8 GB de RAM (mínimo 4 GB) · 10 GB libres en disco"],
             ["Conexión", "Por <b>cable</b> a la red de la escuela (más estable que Wi-Fi)"],
             ["Horario", "Encendido durante la jornada. Si se apaga, nadie puede entrar hasta que se encienda"],
             ["Internet", "Solo para instalar y para actualizar. El uso diario funciona sin internet"],
             ["Permisos", "Una cuenta de Windows con permisos de administrador (solo para instalar)"]],
            [4.5 * cm, 12 * cm]),
      Spacer(1, 8),
      caja("Elija un computador que no se use para clases ni se lleve a otra sala, por ejemplo el de UTP o "
           "secretaría. Pupitre funciona en segundo plano: se puede seguir usando el equipo para otras tareas.",
           AMARILLO, "Consejo"),
      Paragraph("2. Instalar Pupitre", H1),
      pasos([
          "Descargue Pupitre: abra <b>https://github.com/jalvflores-cmd/Pupitre</b>, presione el botón verde "
          "<b>Code</b> y luego <b>Download ZIP</b> (o use el archivo .zip que le entregaron).",
          "Haga clic derecho en el archivo descargado › <b>Extraer todo…</b> y extráigalo en <b>C:\\</b>. "
          "Cambie el nombre de la carpeta a <b>Pupitre</b>, de modo que quede <b>C:\\Pupitre\\manage.py</b>.",
          "Abra la carpeta <b>C:\\Pupitre\\windows</b> y haga doble clic en <b>instalar.bat</b>.",
          "Windows preguntará si permite cambios en el equipo: responda <b>Sí</b>. Si aparece «Windows protegió su "
          "PC», presione <b>Más información</b> y luego <b>Ejecutar de todas formas</b>.",
          "Espere. Si el equipo no tiene Python, el instalador lo descarga solo. Todo puede tardar entre 5 y 15 "
          "minutos según la conexión.",
          "Al terminar se abre el navegador con Pupitre y aparece un acceso directo <b>Pupitre</b> en el escritorio.",
      ]),
      caja("El instalador deja Pupitre configurado para <b>iniciarse solo cada vez que se enciende el equipo</b> "
           "(aunque nadie inicie sesión), abre el puerto 8000 en el firewall de Windows para la red interna y evita "
           "que el equipo se suspenda mientras está enchufado.", SUAVE, "Qué hace el instalador"),
      PageBreak()]

h += [Paragraph("3. Primera configuración", H1),
      p("La primera vez que se abre Pupitre aparece el formulario <b>«Bienvenido(a) a Pupitre»</b>. Complete:"),
      vinetas(["<b>Datos del establecimiento</b>: nombre, RBD, comuna, región, director(a) y jefe(a) de UTP. "
               "Aparecen en los certificados y actas.",
               "<b>Su cuenta</b>: su cargo (Director/a o Jefe/a de UTP), nombre, un nombre de usuario sin espacios "
               "(ej.: <i>jsandoval</i>) y una contraseña segura.",
               "Deje marcada la opción <b>Crear las asignaturas del plan oficial</b>."]),
      Paragraph("Primeros pasos recomendados", H2),
      pasos([
          "<b>Importar la nómina de SIGE</b>: menú <b>Importar Excel</b> › Estudiantes › suba el archivo tal como "
          "se descarga de SIGE. Se crean los cursos y los estudiantes.",
          "<b>Cargar las asignaturas</b>: menú <b>Cursos y notas</b> › botón <b>Cargar plan oficial</b>. Se agregan "
          "las asignaturas de 1° a 8° básico con sus horas. Los talleres JEC se agregan en la página de cada curso.",
          "<b>Crear las cuentas de los funcionarios</b>: menú <b>Configuración</b> › <b>Usuarios</b> › "
          "<b>Agregar usuario</b>. Escriba el nombre de usuario, nombre y contraseña inicial, guarde, y en la "
          "pantalla siguiente elija su <b>rol</b> (Profesor/a, Inspector/a, Convivencia, UTP, etc.).",
          "<b>Asignar profesores</b>: en cada curso, elija el profesor(a) de cada asignatura y guarde. El profesor(a) "
          "jefe se asigna en Configuración › Cursos.",
          "Entregue a cada funcionario su usuario y contraseña inicial; cada uno puede cambiarla en "
          "<b>Cambiar contraseña</b> (abajo a la izquierda).",
      ]),
      Paragraph("Personalizar Pupitre (sin tocar nada técnico)", H2),
      p("En el menú <b>Configuración</b>, Dirección y UTP pueden cambiar cuando quieran:"),
      vinetas(["<b>Datos del establecimiento</b> que aparecen en informes y certificados.",
               "<b>Logo institucional</b>: aparece en el menú, la pantalla de ingreso, las planillas Excel y las "
               "entrevistas. Los documentos oficiales del Mineduc no lo llevan.",
               "<b>Color institucional</b> del menú y los botones, y un <b>texto al pie</b> de los documentos internos.",
               "<b>Protocolos de convivencia</b> y <b>redes de apoyo externas</b>: cambiar nombres, agregar nuevos o "
               "desactivar los que no usan, según su Reglamento Interno."]),
      PageBreak()]

h += [Paragraph("4. Entrar desde los otros computadores", H1),
      p("En cualquier computador, tablet o celular <b>conectado a la red de la escuela</b>, abra el navegador "
        "(Chrome, Edge, Firefox) y escriba la dirección del servidor:"),
      caja("<font face='Courier-Bold' size='13'>http://NOMBRE-DEL-SERVIDOR:8000</font><br/><br/>"
           "El nombre del servidor aparece al final de la instalación. También se ve en el servidor en "
           "<b>Configuración de Windows › Sistema › Acerca de › Nombre del dispositivo</b>."),
      p("Si con el nombre no abre, use la <b>dirección IP</b> del servidor:"),
      pasos(["En el servidor, presione la tecla Windows, escriba <b>cmd</b> y presione Enter.",
             "Escriba <b>ipconfig</b> y presione Enter. Busque <b>Dirección IPv4</b> (ej.: 192.168.1.20).",
             "En los otros computadores abra <b>http://192.168.1.20:8000</b> (con el número de su servidor)."]),
      caja("Para que la dirección IP no cambie, pida a quien administra el router o internet de la escuela que "
           "<b>reserve una IP fija</b> para el servidor. Luego guarde la dirección como favorito en cada computador.",
           AMARILLO, "Importante"),
      p("Pupitre <b>solo es accesible dentro de la red de la escuela</b>. Desde la casa no se puede entrar, "
        "lo que protege la información de los estudiantes."),
      Paragraph("5. Respaldos y Google Drive", H1),
      vinetas(["Pupitre hace <b>un respaldo automático cada día</b> en <b>C:\\Pupitre\\respaldos</b> y guarda los "
               "últimos 30 (los más antiguos se borran solos).",
               "Dirección y UTP ven el menú <b>Respaldos</b>: lista de respaldos, botón <b>Respaldar ahora</b> y "
               "descarga de cualquier respaldo.",
               "<b>Disco externo</b> (opcional): en Respaldos › Configuración escriba la carpeta del disco, por ejemplo "
               "<b>E:\\Respaldos Pupitre</b>. Cada respaldo también se copiará ahí cuando el disco esté conectado."]),
      Paragraph("Copia automática en Google Drive", H2),
      pasos(["Descargue e instale <b>Google Drive para escritorio</b> desde <b>https://www.google.com/drive/download/</b> "
             "en el servidor.",
             "Inicie sesión con la <b>cuenta institucional</b> de la escuela (no una cuenta personal).",
             "Abra Google Drive (ícono en la barra de tareas) › engranaje › <b>Preferencias</b> › <b>Mi computadora</b> "
             "› <b>Agregar carpeta</b>.",
             "Elija <b>C:\\Pupitre\\respaldos</b> y marque <b>Sincronizar con Google Drive</b>. Listo: cada respaldo "
             "nuevo se sube solo a la nube."]),
      PageBreak()]

h += [Paragraph("6. Restaurar un respaldo", H1),
      p("Úselo si se borró información por error o si cambió el computador servidor."),
      pasos(["En el servidor, abra <b>C:\\Pupitre\\windows</b> y haga doble clic en <b>restaurar.bat</b> (responda Sí).",
             "Aparece la lista de respaldos (el 1 es el más reciente). Escriba el número y presione Enter. "
             "También puede arrastrar a la ventana un archivo .zip descargado de Google Drive.",
             "Confirme con <b>s</b>. Pupitre se detiene, recupera los datos y vuelve a iniciarse."]),
      caja("Antes de restaurar, Pupitre guarda automáticamente una copia de los datos actuales "
           "(«antes_de_restaurar»), por si se eligió el respaldo equivocado.", SUAVE),
      Paragraph("Cambiar de computador servidor", H2),
      p("Instale Pupitre en el computador nuevo (sección 2), complete el formulario de bienvenida con cualquier dato "
        "y luego use <b>restaurar.bat</b> con el último respaldo del equipo anterior (copiado desde Google Drive o "
        "un pendrive). Recuerde apagar el servidor antiguo."),
      Paragraph("7. Actualizar a una versión nueva", H1),
      pasos(["Descargue la nueva versión (igual que en la sección 2).",
             "Extraiga el .zip y copie su contenido <b>sobre C:\\Pupitre</b>, aceptando reemplazar los archivos. "
             "Las carpetas <b>datos</b> y <b>respaldos</b> no vienen en el .zip, así que no se tocan.",
             "Haga doble clic en <b>C:\\Pupitre\\windows\\actualizar.bat</b>. Se guarda un respaldo antes de actualizar."]),
      Paragraph("8. Problemas frecuentes", H1),
      tabla([["Problema", "Qué hacer"],
             ["No abre desde otros computadores",
              "Revise que el servidor esté encendido y abra http://localhost:8000 en el propio servidor. Use la IP en "
              "vez del nombre. Si hay antivirus con firewall propio, permita el puerto 8000. En Windows, marque la "
              "red como <b>Privada</b>."],
             ["No abre ni en el servidor", "Ejecute <b>windows\\reiniciar_pupitre.bat</b>. Si sigue igual, reinicie el "
              "equipo. El detalle de errores queda en C:\\Pupitre\\datos\\servidor.log."],
             ["Un funcionario olvidó su contraseña", "Dirección o UTP: Configuración › Usuarios › elegir usuario › "
              "«formulario» de contraseña."],
             ["Se olvidó la contraseña de la única cuenta de Dirección/UTP",
              "En el servidor, ejecute <b>windows\\cambiar_clave.bat</b> y escriba el nombre de usuario."],
             ["Quiero respaldar antes de algo importante", "Menú Respaldos › Respaldar ahora, o "
              "<b>windows\\respaldar_ahora.bat</b>."]],
            [5 * cm, 11.5 * cm]),
      Paragraph("9. Cuidado de los datos personales", H1),
      vinetas(["Pupitre guarda datos personales y sensibles de estudiantes y familias (Ley N° 19.628 y Ley N° 21.430). "
               "Cada funcionario debe usar <b>su propia cuenta</b> y no compartir la contraseña.",
               "Proteja el servidor con una <b>contraseña de Windows</b> y no lo deje con la sesión abierta sin supervisión.",
               "Los respaldos contienen toda la información: guárdelos solo en la cuenta institucional de Google Drive "
               "(con verificación en dos pasos) o en un disco guardado bajo llave.",
               "Al dar de baja el computador servidor, borre la carpeta C:\\Pupitre después de copiar los respaldos."])]


def pie(c, d):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(2 * cm, 1 * cm, "Pupitre · Guía de instalación en el establecimiento")
    c.drawRightString(letter[0] - 2 * cm, 1 * cm, f"Página {d.page}")
    c.restoreState()


salida = Path(__file__).resolve().parent.parent / "docs" / "Guia_instalacion_Pupitre.pdf"
salida.parent.mkdir(exist_ok=True)
SimpleDocTemplate(str(salida), pagesize=letter, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
                  bottomMargin=2 * cm, title="Guía de instalación de Pupitre", author="Pupitre").build(
    h, onFirstPage=pie, onLaterPages=pie)
print(salida)
