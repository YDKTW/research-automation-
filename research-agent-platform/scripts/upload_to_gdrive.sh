#!/usr/bin/env bash
set -u

PROJECTROOT="/opt/research-automation/research-agent-platform"
LOGDIR="${PROJECTROOT}/logs"
UPLOADLOG="${LOGDIR}/upload.log"
ENVFILE="${PROJECTROOT}/.env"

TOPIC="${1:?Usage: bash scripts/upload_to_gdrive.sh <topic> <date>}"
RUNDATE="${2:?Usage: bash scripts/upload_to_gdrive.sh <topic> <date>}"

DATADIR="${PROJECTROOT}/data/${TOPIC}/${RUNDATE}"
ZIPFILE="${PROJECTROOT}/data/${TOPIC}_${RUNDATE}.zip"
REMOTE_DIR="gdrive:research-reports/${TOPIC}/${RUNDATE}"
REMOTE_ZIP_DIR="gdrive:research-reports"

mkdir -p "${LOGDIR}"

log() {
  echo "$(date '+%F %T') $1" | tee -a "${UPLOADLOG}"
}

send_telegram_alert() {
  local message="$1"

  if [[ -f "${ENVFILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENVFILE}"
    set +a
  fi

  if [[ -z "${TELEGRAMBOTTOKEN:-}" || -z "${TELEGRAMCHATID:-}" ]]; then
    log "WARN Telegram alert skipped: TELEGRAMBOTTOKEN or TELEGRAMCHATID missing"
    return 0
  fi

  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAMBOTTOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg chat_id "${TELEGRAMCHATID}" \
      --arg text "${message}" \
      '{chat_id:$chat_id, text:$text}')" >> "${UPLOADLOG}" 2>&1 || \
    log "WARN Telegram alert send failed"
}

log "INFO upload start"
log "INFO topic=${TOPIC}"
log "INFO rundate=${RUNDATE}"
log "INFO datadir=${DATADIR}"
log "INFO zipfile=${ZIPFILE}"

if [[ ! -d "${DATADIR}" ]]; then
  log "ERROR data directory not found: ${DATADIR}"
  send_telegram_alert "❌ Google Drive upload failed
topic=${TOPIC}
date=${RUNDATE}
reason=data directory not found
host=$(hostname)"
  exit 1
fi

log "INFO ensure remote dir ${REMOTE_DIR}"
if ! rclone mkdir "${REMOTE_DIR}" >> "${UPLOADLOG}" 2>&1; then
  log "ERROR failed to create remote dir: ${REMOTE_DIR}"
  send_telegram_alert "❌ Google Drive upload failed
topic=${TOPIC}
date=${RUNDATE}
reason=failed to create remote directory
host=$(hostname)"
  exit 1
fi

log "INFO uploading data directory to ${REMOTE_DIR}"
if ! rclone copy "${DATADIR}" "${REMOTE_DIR}" >> "${UPLOADLOG}" 2>&1; then
  log "ERROR failed to upload data directory"
  send_telegram_alert "❌ Google Drive upload failed
topic=${TOPIC}
date=${RUNDATE}
reason=failed to upload data directory
host=$(hostname)"
  exit 1
fi

if [[ -f "${ZIPFILE}" ]]; then
  log "INFO uploading zip file to ${REMOTE_ZIP_DIR}"
  if ! rclone copy "${ZIPFILE}" "${REMOTE_ZIP_DIR}" >> "${UPLOADLOG}" 2>&1; then
    log "ERROR failed to upload zip file"
    send_telegram_alert "❌ Google Drive upload failed
topic=${TOPIC}
date=${RUNDATE}
reason=failed to upload zip file
host=$(hostname)"
    exit 1
  fi
else
  log "WARN zip file not found: ${ZIPFILE}"
fi

log "INFO verifying remote dir listing ${REMOTE_DIR}"
if ! rclone lsf "${REMOTE_DIR}" >> "${UPLOADLOG}" 2>&1; then
  log "ERROR failed to verify remote dir listing"
  send_telegram_alert "⚠️ Google Drive upload uncertain
topic=${TOPIC}
date=${RUNDATE}
reason=upload finished but remote verification failed
host=$(hostname)"
  exit 1
fi

log "INFO upload completed"
exit 0
