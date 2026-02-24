#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Uso:
  $0

Descricao:
  DESCONTINUADO.
  O repositorio flageemonitor-proxy agora e image-only.
  Nao promovemos mais arquivos para esse repositorio.

  Use apenas:
    /ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

usage
exit 1
