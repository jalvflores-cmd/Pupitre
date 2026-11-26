@echo off
setlocal
title Actualizar Pupitre
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
echo  Deteniendo Pupitre y guardando un respaldo antes de actualizar...
schtasks /end /tn "Pupitre" >nul 2>&1
timeout /t 3 /nobreak >nul
"%PY%" manage.py respaldar --motivo antes_de_actualizar
echo  Instalando componentes nuevos...
"%PY%" -m pip install --quiet -r "%PUPITRE_DIR%\windows\requirements-local.txt" || goto :error
"%PY%" manage.py collectstatic --noinput -v 0 || goto :error
"%PY%" manage.py migrate --noinput -v 0 || goto :error
schtasks /run /tn "Pupitre" >nul
echo.
echo  Pupitre fue actualizado. Sus datos se mantienen.
pause
exit /b 0
:error
echo  Ocurrio un error. Pupitre no se actualizo; vuelva a ejecutar actualizar.bat con internet.
schtasks /run /tn "Pupitre" >nul
pause
exit /b 1
