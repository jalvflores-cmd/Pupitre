@echo off
setlocal
title Restaurar un respaldo de Pupitre
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
echo.
echo  Respaldos disponibles (el 1 es el mas reciente):
echo.
"%PY%" manage.py restaurar
echo.
echo  Escriba el NUMERO del respaldo que quiere recuperar,
echo  o arrastre aqui un archivo .zip de respaldo (por ejemplo, desde Google Drive).
set /p "ELEGIDO=  Respaldo: "
if "%ELEGIDO%"=="" goto :fin
echo.
echo  Deteniendo Pupitre...
schtasks /end /tn "Pupitre" >nul 2>&1
timeout /t 3 /nobreak >nul
"%PY%" manage.py restaurar %ELEGIDO%
echo.
echo  Iniciando Pupitre nuevamente...
schtasks /run /tn "Pupitre" >nul
:fin
pause
