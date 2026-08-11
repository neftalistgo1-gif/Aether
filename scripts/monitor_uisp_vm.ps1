param(
    [string]$UispAddress = "192.168.3.11",
    [int]$Port = 443,
    [int]$FailureThreshold = 3,
    [int]$RecoveryCooldownMinutes = 15,
    [string]$VmName = "UISP"
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$storageDirectory = Join-Path $workspace "backend\private_storage\uisp_monitor"
$statePath = Join-Path $storageDirectory "state.json"
$logPath = Join-Path $storageDirectory "monitor.log"
$recoveryEventsPath = Join-Path $storageDirectory "recovery-events.jsonl"
$vboxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"

New-Item -ItemType Directory -Force -Path $storageDirectory | Out-Null

function Write-MonitorLog([string]$Message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ssK') $Message" | Add-Content -Path $logPath -Encoding utf8
}

function Write-RecoveryEvent([string]$Action, [int]$Failures) {
    [ordered]@{
        occurred_at = (Get-Date).ToString("o")
        event = "uisp_vm_recovery"
        uisp_address = $UispAddress
        failed_checks = $Failures
        action = $Action
    } | ConvertTo-Json -Compress | Add-Content -Path $recoveryEventsPath -Encoding utf8
}

function Test-TcpEndpoint([string]$Address, [int]$TcpPort) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.BeginConnect($Address, $TcpPort, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds(5))) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

$state = @{ consecutive_failures = 0; last_success_at = $null; last_recovery_at = $null }
if (Test-Path $statePath) {
    try {
        $saved = Get-Content $statePath -Raw | ConvertFrom-Json
        $state.consecutive_failures = [int]$saved.consecutive_failures
        $state.last_success_at = $saved.last_success_at
        $state.last_recovery_at = $saved.last_recovery_at
    }
    catch {
        Write-MonitorLog "State file was unreadable; a new state was started."
    }
}

if (Test-TcpEndpoint $UispAddress $Port) {
    if ($state.consecutive_failures -gt 0) {
        Write-MonitorLog "UISP connection recovered after $($state.consecutive_failures) failed check(s)."
    }
    $state.consecutive_failures = 0
    $state.last_success_at = (Get-Date).ToString("o")
}
else {
    $state.consecutive_failures++
    Write-MonitorLog "UISP connection failed ($($state.consecutive_failures)/$FailureThreshold)."
    if ($state.consecutive_failures -ge $FailureThreshold) {
        if (-not (Test-Path $vboxManage)) {
            throw "VBoxManage was not found at $vboxManage"
        }
        $vmInfo = & $vboxManage showvminfo $VmName --machinereadable
        $isRunning = $vmInfo -match '^VMState="running"$'
        if (-not $isRunning) {
            & $vboxManage startvm $VmName --type headless
            if ($LASTEXITCODE -ne 0) {
                throw "VirtualBox could not start the UISP VM"
            }
            Write-MonitorLog "UISP VM started after $FailureThreshold consecutive failed checks."
            Write-RecoveryEvent "start" $FailureThreshold
            $state.consecutive_failures = 0
            $state.last_recovery_at = (Get-Date).ToString("o")
        }
        else {
            $lastRecovery = $null
            if ($state.last_recovery_at) {
                try {
                    $lastRecovery = [DateTimeOffset]$state.last_recovery_at
                }
                catch {
                    Write-MonitorLog "Recovery timestamp was invalid; reset cooldown was skipped."
                }
            }
            if (
                $lastRecovery -and
                (Get-Date) -lt $lastRecovery.LocalDateTime.AddMinutes($RecoveryCooldownMinutes)
            ) {
                Write-MonitorLog "UISP remains unavailable; reset is paused for the $RecoveryCooldownMinutes-minute cooldown."
            }
            else {
            & $vboxManage controlvm $VmName reset
            if ($LASTEXITCODE -ne 0) {
                throw "VirtualBox could not reset the UISP VM"
            }
            Write-MonitorLog "UISP VM reset after $FailureThreshold consecutive failed checks."
            Write-RecoveryEvent "reset" $FailureThreshold
            $state.consecutive_failures = 0
            $state.last_recovery_at = (Get-Date).ToString("o")
            }
        }
    }
}

$state | ConvertTo-Json | Set-Content -Path $statePath -Encoding utf8
