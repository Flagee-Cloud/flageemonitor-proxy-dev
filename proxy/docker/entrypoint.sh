#!/usr/bin/env bash
set -euo pipefail

CONFIG_URL="${ARIUSMONITOR_CONFIG_URL:-}"
if [[ -z "${CONFIG_URL}" && -n "${ARIUSMONITOR_API_URL:-}" ]]; then
  CONFIG_URL="${ARIUSMONITOR_API_URL}/bot/config"
fi
CONFIG_URL="${CONFIG_URL#\"}"
CONFIG_URL="${CONFIG_URL%\"}"
CONFIG_PATH="${ARIUSMONITOR_CONFIG_PATH:-/ariusmonitor/config_bot.json}"
CONFIG_CONF="${ARIUSMONITOR_CONFIG_CONF:-/ariusmonitor/config_bot.conf}"
BOT_TOKEN="${ARIUSMONITOR_TOKEN:-}"
REDE_PARAM="${ARIUSMONITOR_REDE:-}"
RUN_MODE="${RUN_MODE:-daemon}"
REFRESH_CONFIG="${ARIUSMONITOR_CONFIG_REFRESH:-false}"

export ARIUSMONITOR_CONFIG_PATH="${CONFIG_PATH}"
export ARIUSMONITOR_CONFIG_CONF="${CONFIG_CONF}"

if [[ "${RUN_MODE}" == "daemon" && $# -gt 0 ]]; then
  RUN_MODE="manual"
fi

if [[ "${RUN_MODE}" == "daemon" && -z "${ARIUSMONITOR_CONFIG_REFRESH:-}" ]]; then
  REFRESH_CONFIG="true"
fi

log() {
  printf '%s\n' "$*"
}

fetch_config() {
  if [[ -z "${CONFIG_URL}" ]]; then
    log "ARIUSMONITOR_CONFIG_URL vazio; usando config local se existir."
    return 0
  fi

  if [[ -z "${BOT_TOKEN}" ]]; then
    log "ARIUSMONITOR_TOKEN vazio; usando config local se existir."
    return 0
  fi

  local url="${CONFIG_URL}"
  local rede_param="${REDE_PARAM#\"}"
  rede_param="${rede_param%\"}"
  local bot_token="${BOT_TOKEN#\"}"
  bot_token="${bot_token%\"}"
  if [[ -n "${rede_param}" ]]; then
    if [[ "${url}" == *"?"* ]]; then
      url="${url}&rede=${rede_param}"
    else
      url="${url}?rede=${rede_param}"
    fi
  fi

  log "Baixando config_bot.json de ${url}"
  if ! curl -fsSL -H "X-Bot-Token: ${bot_token}" "${url}" -o "${CONFIG_PATH}.tmp"; then
    log "Falha ao baixar config_bot.json."
    return 0
  fi
  mv "${CONFIG_PATH}.tmp" "${CONFIG_PATH}"
}

write_conf() {
  if [[ ! -f "${CONFIG_PATH}" ]]; then
    log "config_bot.json nao encontrado em ${CONFIG_PATH}."
    return 0
  fi

  python3 - <<'PY'
import json
import os
import shlex

config_path = os.environ.get("ARIUSMONITOR_CONFIG_PATH", "/ariusmonitor/config_bot.json")
config_conf = os.environ.get("ARIUSMONITOR_CONFIG_CONF", "/ariusmonitor/config_bot.conf")

with open(config_path, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = []
for key, value in data.items():
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, ensure_ascii=True)
    else:
        rendered = str(value)
    lines.append(f"export {key}={shlex.quote(rendered)}")

with open(config_conf, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
    f.write("\n")
PY
}

if [[ "${REFRESH_CONFIG}" == "true" ]]; then
  fetch_config
fi

write_conf

if [[ "${RUN_MODE}" == "daemon" ]]; then
  python3 /ariusmonitor/scripts/render_cron.py
  exec cron -f
fi

if [[ $# -eq 0 || "${1}" == "--help" ]]; then
  log "Uso: docker run ... <acao> [args]"
  log "Exemplo: docker run ... pdv_install --agent-status 2"
  exit 0
fi

exec python3 /ariusmonitor/runtime/main.py "$@"
