$ErrorActionPreference = "Stop"
$storageDirectory = Join-Path $PSScriptRoot "..\backend\private_storage\uisp_batch"
$tokenPath = Join-Path $storageDirectory "api-token.protected"
$metadataPath = Join-Path $storageDirectory "config.json"

if (-not (Test-Path $tokenPath) -or -not (Test-Path $metadataPath)) {
    throw "Primero ejecuta scripts\set_uisp_batch_token.ps1."
}

$secureToken = Get-Content -LiteralPath $tokenPath -Raw | ConvertTo-SecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    $config = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    $response = Invoke-RestMethod -Uri "$($config.uisp_address)/nms/api/v2.1/devices" -Headers @{ "X-Auth-Token" = $token } -TimeoutSec 15
    $count = @($response).Count
    Write-Host "UISP API conectada. Dispositivos visibles: $count"
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
