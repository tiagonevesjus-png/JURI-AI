param(
    [switch]$SkipSetup
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env.local'
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Arquivo .env.local ausente. Copie .env.local.example e defina as credenciais locais.'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Ambiente Python ausente. Crie .venv e instale requirements-base.txt.'
}

Get-Content -LiteralPath $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $pair = $line.Split('=', 2)
    if ($pair.Count -eq 2) {
        Set-Item -Path ("Env:" + $pair[0].Trim()) -Value $pair[1]
    }
}

Push-Location $root
try {
    if (-not $SkipSetup) {
        & $python manage.py migrate --noinput
        & $python manage.py setup_inicial
        & $python manage.py collectstatic --noinput
    }
    & $python manage.py runserver 127.0.0.1:8000
}
finally {
    Pop-Location
}
