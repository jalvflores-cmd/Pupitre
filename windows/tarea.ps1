# Crea (o actualiza) la tarea programada que inicia Pupitre al encender el computador.
param([Parameter(Mandatory = $true)][string]$Bat)
$accion = New-ScheduledTaskAction -Execute $Bat
$disparador = New-ScheduledTaskTrigger -AtStartup
$opciones = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$cuenta = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "Pupitre" -Action $accion -Trigger $disparador -Settings $opciones `
    -Principal $cuenta -Description "Servidor de Pupitre (gestion curricular)" -Force | Out-Null
