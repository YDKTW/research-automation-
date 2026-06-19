#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/research-automation/research-agent-platform"
REPORT_SCRIPT="$PROJECT_ROOT/scripts/run_report.sh"
TELEGRAM_SCRIPT="$PROJECT_ROOT/scripts/send_telegram_message.py"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/run_and_notify.sh <topic> [date] [--send-report-file]"
  exit 1
fi

TOPIC="$1"
RUN_DATE="${2:-$(date +%F)}"
SEND_REPORT_FILE="${3:-}"

echo "[INFO] Step 1/2: run report"
bash "$REPORT_SCRIPT" "$TOPIC" "$RUN_DATE"

echo "[INFO] Step 2/2: send Telegram notification"
if [ "$SEND_REPORT_FILE" = "--send-report-file" ]; then
  "$PYTHON_BIN" "$TELEGRAM_SCRIPT" \
    --topic "$TOPIC" \
    --date "$RUN_DATE" \
    --send-report-file
else
  "$PYTHON_BIN" "$TELEGRAM_SCRIPT" \
    --topic "$TOPIC" \
    --date "$RUN_DATE"
fi

echo "[INFO] run_and_notify completed successfully"
