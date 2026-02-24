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
CONFIG_CONF="${FLAGEEMONITOR_CONFIG_CONF:-${ARIUSMONITOR_CONFIG_CONF:-/flageemonitor/config_bot.conf}}"
BOT_TOKEN="${FLAGEEMONITOR_TOKEN:-${ARIUSMONITOR_TOKEN:-}}"
REDE_PARAM="${FLAGEEMONITOR_REDE:-${ARIUSMONITOR_REDE:-}}"
RUN_MODE="${RUN_MODE:-daemon}"
REFRESH_CONFIG="${FLAGEEMONITOR_CONFIG_REFRESH:-${ARIUSMONITOR_CONFIG_REFRESH:-false}}"

export FLAGEEMONITOR_CONFIG_PATH="${CONFIG_PATH}"
export FLAGEEMONITOR_CONFIG_CONF="${CONFIG_CONF}"

if [[ "${RUN_MODE}" == "daemon" && $# -gt 0 ]]; then
  RUN_MODE="manual"
fi

if [[ "${RUN_MODE}" == "daemon" && -z "${FLAGEEMONITOR_CONFIG_REFRESH:-${ARIUSMONITOR_CONFIG_REFRESH:-}}" ]]; then
  REFRESH_CONFIG="true"
fi

log() {
  printf '%s\n' "$*"
}

fetch_config() {
  [[ -z "${CONFIG_URL}" ]] && { log "CONFIG_URL vazio; usando config local."; return 0; }
  [[ -z "${BOT_TOKEN}" ]] && { log "TOKEN vazio; usando config local."; return 0; }

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
  [[ ! -f "${CONFIG_PATH}" ]] && { log "config_bot.json nao encontrado em ${CONFIG_PATH}."; return 0; }

  python3 - <<'PY'
import json
import os
import shlex

config_path = os.environ.get("FLAGEEMONITOR_CONFIG_PATH", "/flageemonitor/config_bot.json")
config_conf = os.environ.get("FLAGEEMONITOR_CONFIG_CONF", "/flageemonitor/config_bot.conf")

with open(config_path, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = []
for key, value in data.items():
    rendered = json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)
    lines.append(f"export {key}={shlex.quote(rendered)}")

with open(config_conf, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
    f.write("\n")
PY
}

[[ "${REFRESH_CONFIG}" == "true" ]] && fetch_config
write_conf

if [[ "${RUN_MODE}" == "daemon" ]]; then
  python3 /flageemonitor/scripts/render_cron.py
  exec cron -f
fi

if [[ $# -eq 0 || "${1}" == "--help" ]]; then
  log "Uso: docker run ... <acao> [args]"
  log "Exemplo: docker run ... install_endpoint_agent --agent-status 2"
  exit 0
fi

exec python3 /flageemonitor/runtime/main.py "$@"
