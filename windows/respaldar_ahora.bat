@echo off
title Respaldo de Pupitre
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
"%PY%" manage.py respaldar --motivo manual
pause
