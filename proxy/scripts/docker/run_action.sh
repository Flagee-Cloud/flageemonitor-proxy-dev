#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: run_action.sh <acao> [args]"
  exit 1
fi

. /ariusmonitor/ariusmonitor.env 2>/dev/null || true
. /ariusmonitor/ghcr.env 2>/dev/null || true

IMAGE_NAME="${IMAGE_NAME:-${ARIUSMONITOR_IMAGE:-ghcr.io/flagee-cloud/ariusmonitor-client:latest}}"
GHCR_USER="${GHCR_USER:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"

if [[ -n "${GHCR_USER}" && -n "${GHCR_TOKEN}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
fi

docker_args=(docker run --rm)
if [[ -f /ariusmonitor/config_bot.json ]]; then
  docker_args+=(-v /ariusmonitor/config_bot.json:/ariusmonitor/config_bot.json:ro)
  docker_args+=(-e "ARIUSMONITOR_CONFIG_REFRESH=false")
fi
if [[ -x /usr/bin/zabbix_sender ]]; then
  docker_args+=(-v /usr/bin/zabbix_sender:/usr/bin/zabbix_sender:ro)
fi
[[ -n "${ARIUSMONITOR_TOKEN:-}" ]] && docker_args+=(-e "ARIUSMONITOR_TOKEN=${ARIUSMONITOR_TOKEN}")
[[ -n "${ARIUSMONITOR_REDE:-}" ]] && docker_args+=(-e "ARIUSMONITOR_REDE=${ARIUSMONITOR_REDE}")
[[ -n "${ARIUSMONITOR_CONFIG_URL:-}" ]] && docker_args+=(-e "ARIUSMONITOR_CONFIG_URL=${ARIUSMONITOR_CONFIG_URL}")
[[ -n "${ARIUSMONITOR_CONFIG_REFRESH:-}" ]] && docker_args+=(-e "ARIUSMONITOR_CONFIG_REFRESH=${ARIUSMONITOR_CONFIG_REFRESH}")
[[ -n "${ARIUSMONITOR_CONFIG_PATH:-}" ]] && docker_args+=(-e "ARIUSMONITOR_CONFIG_PATH=${ARIUSMONITOR_CONFIG_PATH}")
[[ -n "${ARIUSMONITOR_CONFIG_CONF:-}" ]] && docker_args+=(-e "ARIUSMONITOR_CONFIG_CONF=${ARIUSMONITOR_CONFIG_CONF}")

exec "${docker_args[@]}" "${IMAGE_NAME}" "$@"
