#!/usr/bin/env bash
set -euo pipefail

CONFIG_URL="${FLAGEEMONITOR_CONFIG_URL:-${ARIUSMONITOR_CONFIG_URL:-}}"
if [[ -z "${CONFIG_URL}" ]]; then
  base="${FLAGEEMONITOR_API_BASE:-${ARIUSMONITOR_API_URL:-}}"
  [[ -n "${base}" ]] && CONFIG_URL="${base}/bot/config"
fi
CONFIG_URL="${CONFIG_URL#\"}"
CONFIG_URL="${CONFIG_URL%\"}"

CONFIG_PATH="${FLAGEEMONITOR_CONFIG_PATH:-${ARIUSMONITOR_CONFIG_PATH:-/flageemonitor/config_bot.json}}"
BOT_TOKEN="${FLAGEEMONITOR_TOKEN:-${ARIUSMONITOR_TOKEN:-}}"
REDE_PARAM="${FLAGEEMONITOR_REDE:-${ARIUSMONITOR_REDE:-}}"
REDE_PARAM="${REDE_PARAM#\"}"
REDE_PARAM="${REDE_PARAM%\"}"
BOT_TOKEN="${BOT_TOKEN#\"}"
BOT_TOKEN="${BOT_TOKEN%\"}"

log() { printf '%s\n' "$*"; }

if [[ -z "${CONFIG_URL}" || -z "${BOT_TOKEN}" ]]; then
  log "CONFIG_URL ou TOKEN ausente; mantendo config atual."
  [[ -f /flageemonitor/scripts/render_cron.py ]] && python3 /flageemonitor/scripts/render_cron.py || true
  exit 0
fi

url="${CONFIG_URL}"
if [[ -n "${REDE_PARAM}" ]]; then
  if [[ "${url}" == *"?"* ]]; then
    url="${url}&rede=${REDE_PARAM}"
  else
    url="${url}?rede=${REDE_PARAM}"
  fi
fi

if ! curl -fsSL -H "X-Bot-Token: ${BOT_TOKEN}" "${url}" -o "${CONFIG_PATH}.tmp"; then
  log "Falha ao baixar config_bot.json; mantendo config atual."
  [[ -f /flageemonitor/scripts/render_cron.py ]] && python3 /flageemonitor/scripts/render_cron.py || true
  exit 0
fi
mv "${CONFIG_PATH}.tmp" "${CONFIG_PATH}"

[[ -f /flageemonitor/scripts/render_cron.py ]] && python3 /flageemonitor/scripts/render_cron.py || true
