#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/research-automation/research-agent-platform"
LOG_DIR="$PROJECT_ROOT/logs"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
UPDATE_SCRIPT="$PROJECT_ROOT/scripts/update_papers_military_general.py"
RUN_AND_NOTIFY_SCRIPT="$PROJECT_ROOT/scripts/run_and_notify.sh"

TOPIC="${1:-軍事通識教育相關研究}"
RUNDATE="${2:-$(date +%F)}"
SEND_REPORT_FILE="${3:---send-report-file}"
REMOTE_NAME="${4:-gdrive}"
REMOTE_DIR="${5:-research-reports}"
DAYS_BACK="${6:-365}"
MAX_RESULTS="${7:-5}"

DATADIR="$PROJECT_ROOT/data/$TOPIC/$RUNDATE"
ZIPFILE="$PROJECT_ROOT/data/${TOPIC}_${RUNDATE}.zip"

mkdir -p "$LOG_DIR" "$PROJECT_ROOT/data"

log() {
  echo "$(date '+%F %T') INFO $*"
}

fail() {
  echo "$(date '+%F %T') ERROR $*" >&2
  exit 1
}

log "scheduled run start | topic=$TOPIC | rundate=$RUNDATE"

cd "$PROJECT_ROOT"

if [ ! -x "$PYTHON_BIN" ]; then
  fail "Python not found: $PYTHON_BIN"
fi

if [ ! -f "$UPDATE_SCRIPT" ]; then
  fail "Update script not found: $UPDATE_SCRIPT"
fi

if [ ! -f "$RUN_AND_NOTIFY_SCRIPT" ]; then
  fail "Run-and-notify script not found: $RUN_AND_NOTIFY_SCRIPT"
fi

log "step 1/4 update papers"
"$PYTHON_BIN" "$UPDATE_SCRIPT" \
  --topic "$TOPIC" \
  --run-date "$RUNDATE" \
  --days-back "$DAYS_BACK" \
  --max-results "$MAX_RESULTS"

log "step 2/4 run report and telegram notify"
bash "$RUN_AND_NOTIFY_SCRIPT" "$TOPIC" "$RUNDATE" "$SEND_REPORT_FILE"

log "step 3/4 prepare zip for google drive"
apt-get update -y >/dev/null 2>&1 || true
apt-get install -y zip rclone >/dev/null 2>&1 || true

[ -d "$DATADIR" ] || fail "Report data directory not found: $DATADIR"

rm -f "$ZIPFILE"
zip -r "$ZIPFILE" "$DATADIR" >/dev/null

[ -f "$ZIPFILE" ] || fail "ZIP file not created: $ZIPFILE"
log "zip created: $ZIPFILE"

log "step 4/4 upload to google drive"
rclone lsd "${REMOTE_NAME}:" >/dev/null 2>&1 || fail "rclone remote not available: ${REMOTE_NAME}: (run 'rclone config' first)"

rclone copy "$ZIPFILE" "${REMOTE_NAME}:${REMOTE_DIR}/"
rclone copy "$DATADIR" "${REMOTE_NAME}:${REMOTE_DIR}/${TOPIC}/${RUNDATE}/"

log "google drive upload done | remote=${REMOTE_NAME}:${REMOTE_DIR}/"
log "scheduled run done"
