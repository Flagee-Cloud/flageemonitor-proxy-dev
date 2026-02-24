#!/usr/bin/env bash
set -euo pipefail

API_BASE_DEFAULT="https://api-ariusmonitor.flagee.cloud/api/ingest"
IMAGE_DEFAULT="ghcr.io/flagee-cloud/flageemonitor-client:latest"
RUNTIME_NAME_DEFAULT="flageemonitor"
CONTAINER_ROOT_DEFAULT="/flageemonitor"

usage() {
  cat <<USAGE
Uso:
  $0 <TOKEN_CLIENTE> [--api-base URL] [--image IMAGE] [--runtime-name NAME] [--container-root PATH] [--ghcr-user USER] [--ghcr-token TOKEN]

Exemplo:
  $0 TOKEN_DO_CLIENTE --runtime-name flageemonitor
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute como root."
  exit 1
fi

CLIENT_TOKEN="$1"
shift

API_BASE="$API_BASE_DEFAULT"
IMAGE_NAME="$IMAGE_DEFAULT"
RUNTIME_NAME="$RUNTIME_NAME_DEFAULT"
CONTAINER_ROOT="$CONTAINER_ROOT_DEFAULT"
GHCR_USER=""
GHCR_TOKEN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base)
      API_BASE="$2"
      shift 2
      ;;
    --image)
      IMAGE_NAME="$2"
      shift 2
      ;;
    --runtime-name)
      RUNTIME_NAME="$2"
      shift 2
      ;;
    --container-root)
      CONTAINER_ROOT="$2"
      shift 2
      ;;
    --ghcr-user)
      GHCR_USER="$2"
      shift 2
      ;;
    --ghcr-token)
      GHCR_TOKEN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento invalido: $1"
      usage
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker nao encontrado. Instale Docker Engine/compat e rode novamente."
  exit 1
fi

if [[ -n "${GHCR_USER}" && -z "${GHCR_TOKEN}" ]]; then
  echo "GHCR_TOKEN ausente. Passe --ghcr-token."
  exit 1
fi
if [[ -n "${GHCR_TOKEN}" && -z "${GHCR_USER}" ]]; then
  echo "GHCR_USER ausente. Passe --ghcr-user."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl start docker >/dev/null 2>&1 || true
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Nao foi possivel acessar o daemon Docker."
  exit 1
fi

CONFIG_DIR="/etc/flageemonitor"
DATA_DIR="/var/lib/flageemonitor"
LOG_DIR="${DATA_DIR}/logs"
UTIL_DIR="${DATA_DIR}/utilities"
CONFIG_PATH="${CONFIG_DIR}/config_bot.json"
ENV_PATH="${CONFIG_DIR}/flageemonitor.env"
GHCR_ENV_PATH="${CONFIG_DIR}/ghcr.env"

install -d -m 700 "$CONFIG_DIR"
install -d -m 755 "$DATA_DIR" "$LOG_DIR" "$UTIL_DIR"
install -d -m 755 /usr/local/bin

CONFIG_URL="${API_BASE}/bot/config"

echo "Baixando config_bot.json..."
if ! curl -fsSL -H "X-Bot-Token: ${CLIENT_TOKEN}" "${CONFIG_URL}" -o "${CONFIG_PATH}"; then
  echo "Falha ao baixar config_bot.json."
  exit 1
fi
chmod 600 "$CONFIG_PATH"

readarray -t config_vals < <(python3 - <<PY
import json
with open('${CONFIG_PATH}', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('PARAM_REDE', ''))
print(data.get('TIMEZONE', 'America/Sao_Paulo'))
PY
)

REDE="${config_vals[0]}"
TIMEZONE="${config_vals[1]}"

if [[ -z "$REDE" ]]; then
  echo "config_bot.json sem PARAM_REDE."
  exit 1
fi

cat <<ENV > "$ENV_PATH"
FLAGEEMONITOR_REDE="${REDE}"
FLAGEEMONITOR_TOKEN="${CLIENT_TOKEN}"
FLAGEEMONITOR_API_BASE="${API_BASE}"
FLAGEEMONITOR_CONFIG_URL="${CONFIG_URL}"
FLAGEEMONITOR_IMAGE="${IMAGE_NAME}"
FLAGEEMONITOR_CONFIG_PATH="${CONTAINER_ROOT}/config_bot.json"
FLAGEEMONITOR_CONTAINER_ROOT="${CONTAINER_ROOT}"
TZ="${TIMEZONE}"
ENV
chmod 600 "$ENV_PATH"

if [[ -n "${GHCR_USER}" && -n "${GHCR_TOKEN}" ]]; then
  cat <<ENV > "$GHCR_ENV_PATH"
GHCR_USER="${GHCR_USER}"
GHCR_TOKEN="${GHCR_TOKEN}"
ENV
  chmod 600 "$GHCR_ENV_PATH"
fi

cat <<'SCRIPT' > /usr/local/bin/flageemonitor-update-config
#!/usr/bin/env bash
set -euo pipefail

. /etc/flageemonitor/flageemonitor.env

url="${FLAGEEMONITOR_CONFIG_URL}"
if [[ -n "${FLAGEEMONITOR_REDE:-}" ]]; then
  if [[ "$url" == *"?"* ]]; then
    url="${url}&rede=${FLAGEEMONITOR_REDE}"
  else
    url="${url}?rede=${FLAGEEMONITOR_REDE}"
  fi
fi

tmp="/etc/flageemonitor/config_bot.json.tmp"
if ! curl -fsSL -H "X-Bot-Token: ${FLAGEEMONITOR_TOKEN}" "$url" -o "$tmp"; then
  echo "Falha ao atualizar config_bot.json"
  exit 1
fi
mv "$tmp" /etc/flageemonitor/config_bot.json
chmod 600 /etc/flageemonitor/config_bot.json
SCRIPT
chmod +x /usr/local/bin/flageemonitor-update-config

cat <<'SCRIPT' > /usr/local/bin/flageemonitor-update-image
#!/usr/bin/env bash
set -euo pipefail

. /etc/flageemonitor/flageemonitor.env
[[ -f /etc/flageemonitor/ghcr.env ]] && . /etc/flageemonitor/ghcr.env

runtime_name="${RUNTIME_NAME:-flageemonitor}"
container_root="${FLAGEEMONITOR_CONTAINER_ROOT:-/flageemonitor}"

if [[ -n "${GHCR_USER:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
fi

docker pull "${FLAGEEMONITOR_IMAGE}"

tmp_container="${runtime_name}-utiltmp"
docker rm -f "$tmp_container" >/dev/null 2>&1 || true
docker create --name "$tmp_container" "${FLAGEEMONITOR_IMAGE}" >/dev/null
mkdir -p /var/lib/flageemonitor/utilities
docker cp "$tmp_container":"${container_root}/utilities/." /var/lib/flageemonitor/utilities/ 2>/dev/null || true
docker rm -f "$tmp_container" >/dev/null 2>&1 || true

docker rm -f "$runtime_name" >/dev/null 2>&1 || true
docker run -d --name "$runtime_name" --restart unless-stopped \
  --env-file /etc/flageemonitor/flageemonitor.env \
  -e "RUNTIME_NAME=${runtime_name}" \
  -v /etc/flageemonitor/config_bot.json:${container_root}/config_bot.json:ro \
  -v /var/lib/flageemonitor/logs:${container_root}/logs \
  -v /var/lib/flageemonitor/utilities:${container_root}/utilities:ro \
  "${FLAGEEMONITOR_IMAGE}"
SCRIPT
chmod +x /usr/local/bin/flageemonitor-update-image

cat <<'SCRIPT' > /usr/local/bin/flageemonitor-run
#!/usr/bin/env bash
set -euo pipefail

runtime_name="${RUNTIME_NAME:-flageemonitor}"
container_root="${FLAGEEMONITOR_CONTAINER_ROOT:-/flageemonitor}"
if [[ $# -lt 1 ]]; then
  echo "Uso: flageemonitor-run <acao> [args]"
  exit 1
fi

exec docker exec "$runtime_name" "${container_root}/run_action.sh" "$@"
SCRIPT
chmod +x /usr/local/bin/flageemonitor-run

cat <<'SCRIPT' > /usr/local/bin/flageemonitor-logs
#!/usr/bin/env bash
set -euo pipefail

runtime_name="${RUNTIME_NAME:-flageemonitor}"
exec docker logs -f "$runtime_name"
SCRIPT
chmod +x /usr/local/bin/flageemonitor-logs

echo "Executando update inicial..."
RUNTIME_NAME="$RUNTIME_NAME" flageemonitor-update-config
RUNTIME_NAME="$RUNTIME_NAME" flageemonitor-update-image

echo "Instalacao concluida."
echo "Container: ${RUNTIME_NAME}"
echo "Comandos: flageemonitor-run | flageemonitor-update-config | flageemonitor-update-image | flageemonitor-logs"
