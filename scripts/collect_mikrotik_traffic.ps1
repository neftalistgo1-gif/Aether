$ErrorActionPreference = "Stop"
$mutex = [Threading.Mutex]::new($false, "AetherMikrotikTrafficCollector")
if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    & docker exec -w /app/backend docker-backend-1 python scripts/collect_mikrotik_traffic.py | Out-Null
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
