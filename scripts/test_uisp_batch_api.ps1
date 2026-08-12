$ErrorActionPreference = "Stop"
$storageDirectory = Join-Path $PSScriptRoot "..\backend\private_storage\uisp_batch"
$tokenPath = Join-Path $storageDirectory "api-token.protected"
$metadataPath = Join-Path $storageDirectory "config.json"

if (-not (Test-Path $tokenPath) -or -not (Test-Path $metadataPath)) {
    throw "Primero ejecuta scripts\set_uisp_batch_token.ps1."
}

$protectedValue = (Get-Content -LiteralPath $tokenPath -Raw).Trim().TrimStart([char]0xFEFF)
$secureToken = $protectedValue | ConvertTo-SecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    $config = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
    # curl handles the local UISP TLS certificate consistently on Windows 10.
    # Passing the header through standard input keeps the token out of process arguments.
    $curlConfig = @"
url = "$($config.uisp_address)/nms/api/v2.1/devices"
insecure
silent
show-error
header = "X-Auth-Token: $token"
"@
    $response = $curlConfig | & curl.exe --config - | ConvertFrom-Json
    $count = @($response).Count
    Write-Host "UISP API conectada. Dispositivos visibles: $count"
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
