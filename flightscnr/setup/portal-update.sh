#!/bin/bash
# Portal-triggered update: git pull, refresh deps, restart flightscnr.service.
# User presets live outside the repo (/var/lib/flightscnr, /etc/flightscnr.env).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="/var/lib/flightscnr"
STATUS_FILE="$DATA_DIR/update-status.json"
LOCK_FILE="$DATA_DIR/update.lock"
LOG_FILE="$DATA_DIR/update.log"

# Detach from the web portal process so systemd restart does not kill the update.
if [ -z "${FLIGHTSCNR_PORTAL_UPDATE:-}" ]; then
    export FLIGHTSCNR_PORTAL_UPDATE=1
    mkdir -p "$DATA_DIR"
    nohup "$0" >>"$LOG_FILE" 2>&1 </dev/null &
    exit 0
fi

write_status() {
    local state="$1"
    local message="${2:-}"
    mkdir -p "$DATA_DIR"
    python3 - "$STATUS_FILE" "$state" "$message" <<'PY'
import json, sys
from datetime import datetime, timezone

path, state, message = sys.argv[1:4]
payload = {
    "state": state,
    "message": message,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)
PY
}

cleanup() {
    local code=$?
    exec 9>&-
    if [ "$code" -eq 0 ]; then
        write_status "success" "Update finished successfully."
    else
        write_status "failed" "Update failed (exit $code). See $LOG_FILE"
    fi
    rm -f "$LOCK_FILE"
    exit "$code"
}

mkdir -p "$DATA_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Update already running" >&2
    exit 1
fi

echo $$ >"$LOCK_FILE"
trap cleanup EXIT

{
    echo ""
    echo "==> Portal update $(date -Iseconds)"
    echo "    Repo: $REPO_ROOT"
} | tee -a "$LOG_FILE"

write_status "running" "Pulling latest changes and restarting…"

if [ ! -x "$REPO_ROOT/install-pi.sh" ]; then
    echo "install-pi.sh not found" | tee -a "$LOG_FILE"
    exit 1
fi

# Reuse install-pi.sh update path (git pull as repo owner, pip sync, service restart).
bash "$REPO_ROOT/install-pi.sh" update 2>&1 | tee -a "$LOG_FILE"
