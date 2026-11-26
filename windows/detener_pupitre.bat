@echo off
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
schtasks /end /tn "Pupitre"
echo Pupitre detenido. Para volver a iniciarlo, reinicie el equipo o ejecute reiniciar_pupitre.bat
pause
