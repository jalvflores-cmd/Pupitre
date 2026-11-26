@echo off
rem Inicia el servidor de Pupitre. Normalmente lo ejecuta Windows al encender el equipo (tarea "Pupitre").
call "%~dp0_comun.bat"
cd /d "%PUPITRE_DIR%"
"%PY%" servidor_local.py
