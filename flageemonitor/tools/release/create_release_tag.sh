#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PUSH_TAG=0

usage() {
  cat <<USAGE
Uso:
  $0 <version> [--push]

Exemplos:
  $0 0.1.0
  $0 0.1.0 --push

Descricao:
  Cria tag anotada no formato flageemonitor-vMAJOR.MINOR.PATCH.
USAGE
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

VERSION="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)
      PUSH_TAG=1
      shift
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

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Versao invalida: $VERSION"
  echo "Formato esperado: MAJOR.MINOR.PATCH (ex.: 0.1.0)"
  exit 1
fi

TAG="flageemonitor-v${VERSION}"

if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Diretorio raiz nao e um repositorio git valido: $ROOT_DIR"
  exit 1
fi

if git -C "$ROOT_DIR" rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag ja existe localmente: $TAG"
  exit 1
fi

if git -C "$ROOT_DIR" ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "Tag ja existe no remoto origin: $TAG"
  exit 1
fi

SOURCE_SHA="$(git -C "$ROOT_DIR" rev-parse HEAD)"
SOURCE_SHORT="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
DATE_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

MSG="Release ${TAG}

Source: ${SOURCE_SHORT} (${SOURCE_SHA})
Created at: ${DATE_UTC}
"

git -C "$ROOT_DIR" tag -a "$TAG" -m "$MSG"
echo "Tag criada: $TAG -> $SOURCE_SHORT"

if [[ "$PUSH_TAG" -eq 1 ]]; then
  git -C "$ROOT_DIR" push origin "$TAG"
  echo "Tag publicada em origin: $TAG"
else
  echo "Push nao realizado. Use --push para publicar."
fi
