#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/flagee-cloud/ariusmonitor-client}"
TAG="${TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD)}"
GHCR_USER="${GHCR_USER:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
RUNTIME_DIR="$ROOT_DIR/proxy/runtime"

if [[ ! -f "$ROOT_DIR/proxy/docker/Dockerfile" ]]; then
  echo "Dockerfile nao encontrado em $ROOT_DIR/proxy/docker/Dockerfile"
  echo "Execute este script a partir de /ariusmonitor/proxy/scripts/docker"
  exit 1
fi

if [[ -z "${IMAGE_NAME}" ]]; then
  echo "IMAGE_NAME nao definido."
  exit 1
fi

verify_pyarmor_runtime() {
  if [[ ! -d "$RUNTIME_DIR" ]]; then
    echo "Runtime nao encontrado em $RUNTIME_DIR"
    echo "Execute o build de protecao antes do publish: /ariusmonitor/build/build_protegido.sh"
    exit 1
  fi

  if [[ ! -f "$RUNTIME_DIR/pyarmor_runtime_000000/pyarmor_runtime.so" ]]; then
    echo "Runtime PyArmor ausente em $RUNTIME_DIR/pyarmor_runtime_000000/pyarmor_runtime.so"
    echo "Abortando publish para evitar envio de runtime sem protecao."
    exit 1
  fi

  local unprotected
  unprotected="$(find "$RUNTIME_DIR" -type f -name '*.py' ! -path '*/__pycache__/*' -exec grep -L '__pyarmor__' {} + || true)"
  if [[ -n "$unprotected" ]]; then
    echo "Arquivos Python sem marcador PyArmor encontrados no runtime:"
    echo "$unprotected"
    echo "Abortando publish. Regerar runtime protegido antes de publicar."
    exit 1
  fi
}

verify_pyarmor_runtime

if [[ -n "${GHCR_USER}" && -n "${GHCR_TOKEN}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
fi

docker build -f "$ROOT_DIR/proxy/docker/Dockerfile" \
  -t "${IMAGE_NAME}:${TAG}" \
  -t "${IMAGE_NAME}:latest" \
  "$ROOT_DIR/proxy"
docker push "${IMAGE_NAME}:${TAG}"
docker push "${IMAGE_NAME}:latest"

echo "Publicado: ${IMAGE_NAME}:${TAG} e :latest"
