param(
    [string]$ApiUrl = 'https://tiagonevesadv.com.br',
    [switch]$SkipSetup
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'djen-bridge.ps1'
if (-not (Test-Path -LiteralPath $scriptPath)) { throw "Arquivo não encontrado: $scriptPath" }

if (-not $SkipSetup) {
    & $scriptPath -ApiUrl $ApiUrl -Setup
}

$arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '" -ApiUrl "' + $ApiUrl + '"'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'JURI-AI Ponte DJEN Brasil' -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Consulta o Comunica PJe pelo IP brasileiro e sincroniza o JURI-AI.' `
    -Force | Out-Null
Start-ScheduledTask -TaskName 'JURI-AI Ponte DJEN Brasil'
Write-Host 'Ponte DJEN instalada e iniciada. A sincronização será repetida a cada 15 minutos.'
