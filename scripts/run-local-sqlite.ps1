$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env.local'
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Arquivo .env.local ausente.' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Ambiente Python ausente.' }

$allowed = @('ESCRITORIO_NOME', 'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS',
    'CSRF_TRUSTED_ORIGINS', 'PRIMARY_DOMAIN', 'ANTHROPIC_API_KEY',
    'OPENAI_API_KEY', 'IA_EMBEDDING_BACKEND', 'IA_CLAUDE_MODEL', 'Q_SYNC')
Get-Content -LiteralPath $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $pair = $line.Split('=', 2)
    if ($pair.Count -eq 2 -and $allowed -contains $pair[0].Trim()) {
        Set-Item -Path ("Env:" + $pair[0].Trim()) -Value $pair[1]
    }
}

Push-Location $root
try { & $python manage.py runserver 127.0.0.1:8000 --noreload }
finally { Pop-Location }
