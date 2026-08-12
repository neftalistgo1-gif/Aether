param(
    [string]$UispAddress = "https://192.168.3.11",
    [string]$StorageDirectory = (Join-Path $PSScriptRoot "..\backend\private_storage\uisp_batch")
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $StorageDirectory | Out-Null
$tokenPath = Join-Path $StorageDirectory "api-token.protected"
$metadataPath = Join-Path $StorageDirectory "config.json"

$secureToken = Read-Host "Pega el token de UISP (no se mostrará)" -AsSecureString
if ($secureToken.Length -eq 0) {
    throw "No se recibió un token."
}

# Windows protects this value for the current local user. It is intentionally
# stored outside the repository and cannot be read by another Windows account.
$secureToken | ConvertFrom-SecureString | Set-Content -LiteralPath $tokenPath -Encoding utf8
@{
    uisp_address = $UispAddress.TrimEnd("/")
    saved_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

Write-Host "Token guardado localmente y protegido para este usuario de Windows."
