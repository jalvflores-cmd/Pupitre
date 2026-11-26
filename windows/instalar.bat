@echo off
setlocal EnableExtensions
title Instalacion de Pupitre
rem Pedir permisos de administrador si no los tiene
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
echo.
echo  ==========================================================
echo     PUPITRE - Instalacion en el computador del establecimiento
echo  ==========================================================
echo.
echo  Carpeta de instalacion: %PUPITRE_DIR%
echo.

rem 1. Buscar Python 3.10 o superior
set "PYBASE="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PYBASE (
    py -%%V -c "import sys" >nul 2>&1 && set "PYBASE=py -%%V"
  )
)
if not defined PYBASE (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PYBASE=python"
)
if not defined PYBASE (
  echo  [1/6] Python no esta instalado. Instalando Python 3.12 ^(puede tardar unos minutos^)...
  winget install -e --id Python.Python.3.12 --scope machine --silent --accept-package-agreements --accept-source-agreements
  if exist "%ProgramFiles%\Python312\python.exe" set "PYBASE="%ProgramFiles%\Python312\python.exe""
  if not defined PYBASE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYBASE="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
)
if not defined PYBASE (
  echo.
  echo  No se pudo instalar Python automaticamente.
  echo  Descarguelo desde https://www.python.org/downloads/ ^(marque "Add python.exe to PATH"^)
  echo  y vuelva a ejecutar instalar.bat
  pause
  exit /b 1
)
echo  [1/6] Python encontrado: %PYBASE%

rem 2. Entorno de Pupitre
if not exist "%PY%" (
  echo  [2/6] Preparando el entorno de Pupitre...
  %PYBASE% -m venv "%PUPITRE_DIR%\.venv" || goto :error
) else (
  echo  [2/6] Entorno de Pupitre ya existe.
)
echo  [3/6] Instalando componentes ^(requiere internet, solo esta vez^)...
"%PY%" -m pip install --quiet --upgrade pip
"%PY%" -m pip install --quiet -r "%PUPITRE_DIR%\windows\requirements-local.txt" || goto :error

echo  [4/6] Preparando la base de datos...
"%PY%" manage.py collectstatic --noinput -v 0 || goto :error
"%PY%" manage.py migrate --noinput -v 0 || goto :error

echo  [5/6] Configurando el arranque automatico, la red y la energia...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PUPITRE_DIR%\windows\tarea.ps1" -Bat "%PUPITRE_DIR%\windows\iniciar_pupitre.bat" || goto :error
netsh advfirewall firewall delete rule name="Pupitre" >nul 2>&1
netsh advfirewall firewall add rule name="Pupitre" dir=in action=allow protocol=TCP localport=8000 profile=any >nul
rem El servidor no debe suspenderse mientras esta enchufado
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change hibernate-timeout-ac 0 >nul 2>&1
rem Acceso directo en el escritorio
(echo [InternetShortcut]& echo URL=http://localhost:8000/)> "%PUBLIC%\Desktop\Pupitre.url"

echo  [6/6] Iniciando Pupitre...
schtasks /end /tn "Pupitre" >nul 2>&1
schtasks /run /tn "Pupitre" >nul
timeout /t 8 /nobreak >nul
start "" http://localhost:8000/

echo.
echo  ==========================================================
echo   Listo. Pupitre quedo instalado y arranca solo con el equipo.
echo.
echo   En ESTE computador:      http://localhost:8000
echo   En los demas de la red:  http://%COMPUTERNAME%:8000
echo   ^(si no abre, use la direccion IP de este equipo; ver guia^)
echo.
echo   Los respaldos se guardan en: %PUPITRE_DIR%\respaldos
echo  ==========================================================
pause
exit /b 0

:error
echo.
echo  Ocurrio un error durante la instalacion. Revise su conexion a internet y vuelva a intentarlo.
echo  Si el problema continua, envie una foto de esta ventana a quien le ayuda con la instalacion.
pause
exit /b 1
