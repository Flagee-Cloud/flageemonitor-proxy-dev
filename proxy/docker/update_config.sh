#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '%s\n' "$*"
}

CONFIG_URL="${ARIUSMONITOR_CONFIG_URL:-}"
if [[ -z "${CONFIG_URL}" && -n "${ARIUSMONITOR_API_URL:-}" ]]; then
  CONFIG_URL="${ARIUSMONITOR_API_URL}/bot/config"
fi

CONFIG_URL="${CONFIG_URL#\"}"
CONFIG_URL="${CONFIG_URL%\"}"
CONFIG_PATH="${ARIUSMONITOR_CONFIG_PATH:-/ariusmonitor/config_bot.json}"
BOT_TOKEN="${ARIUSMONITOR_TOKEN:-}"
REDE_PARAM="${ARIUSMONITOR_REDE:-}"

# Normaliza aspas acidentais no valor da rede.
REDE_PARAM="${REDE_PARAM#\"}"
REDE_PARAM="${REDE_PARAM%\"}"
BOT_TOKEN="${BOT_TOKEN#\"}"
BOT_TOKEN="${BOT_TOKEN%\"}"

if [[ -z "${CONFIG_URL}" || -z "${BOT_TOKEN}" ]]; then
  log "CONFIG_URL ou ARIUSMONITOR_TOKEN ausente; mantendo config atual."
  if [[ -f /ariusmonitor/scripts/render_cron.py ]]; then
    python3 /ariusmonitor/scripts/render_cron.py || true
  fi
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
  if [[ -f /ariusmonitor/scripts/render_cron.py ]]; then
    python3 /ariusmonitor/scripts/render_cron.py || true
  fi
  exit 0
fi
mv "${CONFIG_PATH}.tmp" "${CONFIG_PATH}"

if [[ -f /ariusmonitor/scripts/render_cron.py ]]; then
  python3 /ariusmonitor/scripts/render_cron.py || true
fi
