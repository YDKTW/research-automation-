#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/research-automation/research-agent-platform"
LOG_DIR="$PROJECT_ROOT/logs"
TOPIC="軍事通識教育相關研究"
RUN_DATE="$(date +%F)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"

echo "[$(date '+%F %T')] [INFO] scheduled run start: $TOPIC / $RUN_DATE"

echo "[$(date '+%F %T')] [INFO] step 1/2 update papers"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/update_papers_military_general.py" \
  --topic "$TOPIC" \
  --run-date "$RUN_DATE" \
  --days-back 365 \
  --max-results 5

echo "[$(date '+%F %T')] [INFO] step 2/2 run report and notify"
bash "$PROJECT_ROOT/scripts/run_and_notify.sh" "$TOPIC" "$RUN_DATE" --send-report-file

echo "[$(date '+%F %T')] [INFO] scheduled run done"
