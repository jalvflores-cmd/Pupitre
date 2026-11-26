@echo off
rem Variables comunes para los scripts de Pupitre (no ejecutar directamente).
set "PUPITRE_DIR=%~dp0.."
for %%I in ("%PUPITRE_DIR%") do set "PUPITRE_DIR=%%~fI"
set "PUPITRE_LOCAL=true"
set "PY=%PUPITRE_DIR%\.venv\Scripts\python.exe"
set "PYTHONUTF8=1"
chcp 65001 >nul
