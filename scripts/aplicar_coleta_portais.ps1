<#
Aplica a atualização local do JURI-AI após uma coleta em portais externos.

Não envia petições, não altera processos nos tribunais e não usa certificado.
Ele só reconstrói a aplicação, aplica a migração local e registra a coleta
auditável já lida no eLaw/PJe TRT16.
#>
[CmdletBinding()]
param(
    [string]$Usuario = 'tiagoneves.jus@gmail.com'
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop não está disponível. Abra-o, aguarde ficar em execução e tente novamente.'
}
if (-not (Test-Path '.env.local')) {
    throw 'Arquivo .env.local não encontrado.'
}

Write-Host 'Reconstruindo os serviços locais do JURI-AI...' -ForegroundColor Cyan
docker compose --env-file .env.local -f docker-compose.local.yml up --build -d web db djen-monitor google-monitor drive-clientes-monitor datajud-monitor triagem-monitor prazos-monitor backup
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível iniciar os serviços Docker.' }

Write-Host 'Aplicando a migração da fila de coletas...' -ForegroundColor Cyan
docker compose --env-file .env.local -f docker-compose.local.yml exec -T web python manage.py migrate gestao
if ($LASTEXITCODE -ne 0) { throw 'A migração do banco falhou.' }

Write-Host 'Registrando a coleta em modo auditável...' -ForegroundColor Cyan
docker compose --env-file .env.local -f docker-compose.local.yml exec -T web python manage.py importar_coleta_inicial_portais --user $Usuario
if ($LASTEXITCODE -ne 0) { throw 'O registro da coleta falhou.' }

Write-Host ''
Write-Host 'Concluído. Abra: http://10.221.180.94:8000/processos/coletados/' -ForegroundColor Green
