# Starts both the backend (uvicorn, port 8001) and frontend (bun dev, port
# 3000), killing anything already listening on those ports first so this is
# safe to re-run. Logs go to .run/backend.log and .run/frontend.log; PIDs
# are written to .run/*.pid so stop.ps1 can find them.
#
# Usage: .\scripts\start.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $root ".run"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Stop-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($ownerPid in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        try { Stop-Process -Id $ownerPid -Force -Confirm:$false -ErrorAction Stop } catch {}
    }
}

function Wait-Http($url, $timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host "Stopping anything already on 8001/3000..."
Stop-Port 8001
Stop-Port 3000
Start-Sleep -Seconds 1

Write-Host "Starting backend (uvicorn :8001)..."
$backendLog = Join-Path $runDir "backend.log"
$backendErrLog = Join-Path $runDir "backend.err.log"
$backend = Start-Process -FilePath "uv" `
    -ArgumentList "run", "uvicorn", "app.main:app", "--port", "8001" `
    -WorkingDirectory (Join-Path $root "backend") `
    -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrLog `
    -WindowStyle Hidden -PassThru
$backend.Id | Out-File -FilePath (Join-Path $runDir "backend.pid") -Encoding utf8 -NoNewline

Write-Host "Starting frontend (bun dev :3000)..."
$frontendLog = Join-Path $runDir "frontend.log"
$frontendErrLog = Join-Path $runDir "frontend.err.log"
$frontend = Start-Process -FilePath "bun" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory (Join-Path $root "frontend") `
    -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrLog `
    -WindowStyle Hidden -PassThru
$frontend.Id | Out-File -FilePath (Join-Path $runDir "frontend.pid") -Encoding utf8 -NoNewline

Write-Host "Waiting for backend..."
if (Wait-Http "http://127.0.0.1:8001/openapi.json" 60) {
    Write-Host "  backend up: http://localhost:8001"
} else {
    Write-Host "  backend did not come up in time - check $backendLog"
}

Write-Host "Waiting for frontend..."
if (Wait-Http "http://127.0.0.1:3000" 30) {
    Write-Host "  frontend up: http://localhost:3000"
} else {
    Write-Host "  frontend did not come up in time - check $frontendLog"
}

Write-Host ""
Write-Host "Logs: $runDir\backend.log / backend.err.log, $runDir\frontend.log / frontend.err.log"
Write-Host "Stop both with: .\scripts\stop.ps1"
