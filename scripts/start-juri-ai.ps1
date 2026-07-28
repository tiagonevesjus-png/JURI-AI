# Inicia o Docker Desktop e a pilha local do JURI-AI no logon do Windows.
$ErrorActionPreference = 'Stop'

$raizProjeto = Split-Path -Parent $PSScriptRoot
$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$dockerCli = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'

if (!(Test-Path -LiteralPath $dockerDesktop) -or !(Test-Path -LiteralPath $dockerCli)) {
    throw 'Docker Desktop não foi encontrado neste computador.'
}

Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
for ($tentativa = 0; $tentativa -lt 36; $tentativa++) {
    & $dockerCli version --format '{{.Server.Version}}' 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 5
}
if ($LASTEXITCODE -ne 0) {
    throw 'O Docker Desktop não ficou disponível dentro de três minutos.'
}

Set-Location $raizProjeto
& $dockerCli compose --env-file .env.local -f docker-compose.local.yml up -d
