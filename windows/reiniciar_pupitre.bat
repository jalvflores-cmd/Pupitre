@echo off
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
schtasks /end /tn "Pupitre" >nul 2>&1
timeout /t 3 /nobreak >nul
schtasks /run /tn "Pupitre"
echo Pupitre reiniciado. Espere unos segundos y abra http://localhost:8000
pause
