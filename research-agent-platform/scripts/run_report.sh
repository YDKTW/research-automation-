#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/research-automation/research-agent-platform"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
RUNNER="$PROJECT_ROOT/apps/report-generator/run_dify_workflow.py"

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/run_report.sh <topic> [date]"
  exit 1
fi

TOPIC="$1"
RUN_DATE="${2:-$(date +%F)}"
DATA_DIR="$PROJECT_ROOT/data/$TOPIC/$RUN_DATE"
PAPERS_FILE="$DATA_DIR/papers.json"

echo "[INFO] project_root: $PROJECT_ROOT"
echo "[INFO] topic: $TOPIC"
echo "[INFO] run_date: $RUN_DATE"
echo "[INFO] data_dir: $DATA_DIR"

mkdir -p "$DATA_DIR"

if [ ! -f "$PAPERS_FILE" ]; then
  echo "[ERROR] papers.json not found: $PAPERS_FILE"
  exit 1
fi

cd "$PROJECT_ROOT"

"$PYTHON_BIN" "$RUNNER" \
  --topic "$TOPIC" \
  --date "$RUN_DATE" \
  --data-dir "$DATA_DIR"

echo "[INFO] report workflow finished"
echo "[INFO] output directory: $DATA_DIR"
