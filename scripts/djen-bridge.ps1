param(
    [string]$ApiUrl = 'https://tiagonevesadv.com.br',
    [switch]$Setup
)

$ErrorActionPreference = 'Stop'
$bridgeDir = Join-Path $env:LOCALAPPDATA 'JuriAI'
$credentialFile = Join-Path $bridgeDir 'djen-bridge-token.txt'
$logFile = Join-Path $bridgeDir 'djen-bridge.log'
New-Item -ItemType Directory -Path $bridgeDir -Force | Out-Null

if ($Setup) {
    $token = Read-Host 'Token da ponte DJEN' -AsSecureString
    $token | ConvertFrom-SecureString | Set-Content -LiteralPath $credentialFile -Encoding UTF8
    Write-Host 'Token protegido pelo Windows e salvo para o usuário atual.'
    exit 0
}

function Write-BridgeLog([string]$Message) {
    if ((Test-Path -LiteralPath $logFile) -and (Get-Item -LiteralPath $logFile).Length -gt 2MB) {
        Move-Item -LiteralPath $logFile -Destination ($logFile + '.old') -Force
    }
    Add-Content -LiteralPath $logFile -Value ((Get-Date).ToString('s') + ' ' + $Message) -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $credentialFile)) {
    throw 'Execute djen-bridge.ps1 -Setup antes da primeira sincronização.'
}

$secureToken = Get-Content -LiteralPath $credentialFile -Raw | ConvertTo-SecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $headers = @{ 'X-DJEN-Bridge-Token' = $plainToken }
    $config = Invoke-RestMethod -Uri ($ApiUrl.TrimEnd('/') + '/integracoes/djen/pendente/') -Headers $headers -Method Get -TimeoutSec 30

    if ($null -ne $config.solicitacao) {
        $inicio = [string]$config.solicitacao.inicio
        $fim = [string]$config.solicitacao.fim
        $solicitacaoId = $config.solicitacao.id
    } else {
        $fim = (Get-Date).ToString('yyyy-MM-dd')
        $inicio = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
        $solicitacaoId = $null
    }

    $query = @{
        numeroOab = [string]$config.numero_oab
        ufOab = [string]$config.uf_oab
        dataDisponibilizacaoInicio = $inicio
        dataDisponibilizacaoFim = $fim
        pagina = 1
        itensPorPagina = 100
        meio = 'D'
    }
    $djen = Invoke-RestMethod -Uri 'https://comunicaapi.pje.jus.br/api/v1/comunicacao' -Body $query -Method Get -TimeoutSec 45
    $payload = @{ solicitacao_id = $solicitacaoId; items = @($djen.items) } | ConvertTo-Json -Depth 30 -Compress
    $resultado = Invoke-RestMethod -Uri ($ApiUrl.TrimEnd('/') + '/integracoes/djen/importar/') -Headers $headers -ContentType 'application/json' -Body $payload -Method Post -TimeoutSec 45
    Write-BridgeLog ("Sincronização concluída: {0} nova(s), {1} total." -f $resultado.novas, $resultado.total)
} catch {
    Write-BridgeLog ('ERRO: ' + $_.Exception.Message)
    throw
} finally {
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $plainToken = $null
}
