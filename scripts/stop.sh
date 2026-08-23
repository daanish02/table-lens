#!/usr/bin/env bash
# Stops the backend/frontend processes started by start.sh.
#
# Usage: ./scripts/stop.sh (run from anywhere, resolves repo root itself)
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_dir="$root/.run"

kill_pidfile() {
    local name="$1"
    local pid_file="$run_dir/$name.pid"
    [ -f "$pid_file" ] || return 0
    local pid
    pid=$(cat "$pid_file")
    if [ -n "$pid" ]; then
        if taskkill //F //PID "$pid" >/dev/null 2>&1; then
            echo "Stopped $name (pid $pid)"
        else
            echo "$name (pid $pid) was not running"
        fi
    fi
    rm -f "$pid_file"
}

kill_port() {
    local port="$1"
    local pids
    pids=$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$port " | awk '{print $NF}' | sort -u || true)
    for pid in $pids; do
        taskkill //F //PID "$pid" >/dev/null 2>&1 || true
    done
}

kill_pidfile "backend"
kill_pidfile "frontend"

# Backend can spawn a child uvicorn worker under a different PID — sweep the
# ports too, in case the pidfile only caught the parent process.
kill_port 8001
kill_port 3000

echo "Done."
