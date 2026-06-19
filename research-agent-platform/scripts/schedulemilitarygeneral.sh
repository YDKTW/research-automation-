#!/usr/bin/env bash
set -euo pipefail

PROJECTROOT="/opt/research-automation/research-agent-platform"
LOGDIR="${PROJECTROOT}/logs"
MAINLOG="${LOGDIR}/schedulemilitarygeneral.log"

TOPIC="軍事通識教育相關研究"
RUNDATE="${1:-$(date +%F)}"
PYTHONBIN="${PROJECTROOT}/.venv/bin/python"

mkdir -p "${LOGDIR}"

log() {
  echo "$(date '+%F %T') $1" | tee -a "${MAINLOG}"
}

cd "${PROJECTROOT}"

log "INFO scheduled run start"
log "INFO topic=${TOPIC}"
log "INFO rundate=${RUNDATE}"

log "INFO step 1/3 update papers"
"${PYTHONBIN}" "${PROJECTROOT}/scripts/update_papers_military_general.py" \
  --topic "${TOPIC}" \
  --run-date "${RUNDATE}" \
  --days-back 365 \
  --max-results 5 2>&1 | tee -a "${MAINLOG}"

log "INFO step 2/3 run report and notify"
bash "${PROJECTROOT}/scripts/run_and_notify.sh" "${TOPIC}" "${RUNDATE}" --send-report-file 2>&1 | tee -a "${MAINLOG}"

log "INFO step 3/3 upload to Google Drive"
if bash "${PROJECTROOT}/scripts/upload_to_gdrive.sh" "${TOPIC}" "${RUNDATE}" 2>&1 | tee -a "${MAINLOG}"; then
  log "INFO Google Drive upload succeeded"
else
  log "WARN Google Drive upload failed"
fi

log "INFO scheduled run done"
