# Stops the backend/frontend processes started by start.ps1.
#
# Usage: .\stop.ps1

$root = $PSScriptRoot
$runDir = Join-Path $root ".run"

function Stop-Pidfile($name) {
    $pidFile = Join-Path $runDir "$name.pid"
    if (-not (Test-Path $pidFile)) { return }
    $processId = Get-Content $pidFile -Raw
    if ($processId) {
        try {
            Stop-Process -Id ([int]$processId) -Force -Confirm:$false -ErrorAction Stop
            Write-Host "Stopped $name (pid $processId)"
        } catch {
            Write-Host "$name (pid $processId) was not running"
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Stop-Pidfile "backend"
Stop-Pidfile "frontend"

# Backend can spawn a child uvicorn worker under a different PID — sweep the
# ports too, in case the pidfile only caught the parent.
foreach ($port in 8001, 3000) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($ownerPid in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        try { Stop-Process -Id $ownerPid -Force -Confirm:$false -ErrorAction Stop } catch {}
    }
}

Write-Host "Done."
