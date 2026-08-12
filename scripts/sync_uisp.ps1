$ErrorActionPreference = "Stop"
$mutex = New-Object System.Threading.Mutex($false, "AetherUISPSync")
if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    docker exec -w /app/backend docker-backend-1 python scripts/sync_uisp.py | Out-Null
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
