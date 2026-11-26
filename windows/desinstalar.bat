@echo off
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
echo Se quitara el arranque automatico de Pupitre. Las carpetas "datos" y "respaldos" NO se borran.
pause
schtasks /end /tn "Pupitre" >nul 2>&1
schtasks /delete /tn "Pupitre" /f
netsh advfirewall firewall delete rule name="Pupitre" >nul 2>&1
echo Listo. Puede borrar la carpeta de Pupitre cuando quiera (guarde antes la carpeta "respaldos").
pause
