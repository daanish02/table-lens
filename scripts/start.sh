#!/usr/bin/env bash
# Starts both the backend (uvicorn, port 8001) and frontend (bun dev, port
# 3000), killing anything already listening on those ports first so this is
# safe to re-run. Logs go to .run/backend.log and .run/frontend.log; PIDs
# are written to .run/*.pid so stop.sh can find them.
#
# Usage: ./scripts/start.sh (run from anywhere, resolves repo root itself)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_dir="$root/.run"
mkdir -p "$run_dir"

# Single .env convention — one file at the repo root, not a separate
# frontend/.env.local. Exporting it into the actual process environment
# here (rather than relying on Next's own build-time env loading, which
# doesn't reliably see env set from outside its own process — confirmed
# via testing) means both the backend and frontend just inherit it
# naturally, regardless of what either framework does internally.
if [ -f "$root/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$root/.env"
    set +a
fi

kill_port() {
    local port="$1"
    local pids
    # netstat is the reliable way to map a port to a PID on Windows (git-bash
    # has no lsof/ss by default); -ano gives numeric addresses + owning PID.
    pids=$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$port " | awk '{print $NF}' | sort -u || true)
    for pid in $pids; do
        taskkill //F //PID "$pid" >/dev/null 2>&1 || true
    done
}

wait_http() {
    local url="$1"
    local timeout="$2"
    local waited=0
    while [ "$waited" -lt "$timeout" ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200"; then
            return 0
        fi
        sleep 0.5
        waited=$((waited + 1))
    done
    return 1
}

echo "Stopping anything already on 8001/3000..."
kill_port 8001
kill_port 3000
sleep 1

echo "Starting backend (uvicorn :8001)..."
(cd "$root/backend" && nohup uv run uvicorn app.main:app --port 8001 > "$run_dir/backend.log" 2>&1 &
 echo $! > "$run_dir/backend.pid")

echo "Starting frontend (bun dev :3000)..."
(cd "$root/frontend" && nohup bun run dev > "$run_dir/frontend.log" 2>&1 &
 echo $! > "$run_dir/frontend.pid")

echo "Waiting for backend..."
if wait_http "http://127.0.0.1:8001/openapi.json" 120; then
    echo "  backend up: http://localhost:8001"
else
    echo "  backend did not come up in time - check $run_dir/backend.log"
fi

echo "Waiting for frontend..."
if wait_http "http://127.0.0.1:3000" 60; then
    echo "  frontend up: http://localhost:3000"
else
    echo "  frontend did not come up in time - check $run_dir/frontend.log"
fi

echo ""
echo "Logs: $run_dir/backend.log, $run_dir/frontend.log"
echo "Stop both with: ./scripts/stop.sh"
