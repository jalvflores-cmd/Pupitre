@echo off
title Cambiar la contrasena de un usuario de Pupitre
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
echo.
echo  Use esto solo si olvido la contrasena y no hay otra cuenta de Direccion o UTP que pueda cambiarla.
echo.
set /p "USUARIO=  Nombre de usuario: "
if "%USUARIO%"=="" goto :fin
"%PY%" manage.py changepassword "%USUARIO%"
:fin
pause
