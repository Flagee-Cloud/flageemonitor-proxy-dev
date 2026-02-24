#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-${ARIUSMONITOR_IMAGE:-ghcr.io/flagee-cloud/ariusmonitor-client:latest}}"
GHCR_USER="${GHCR_USER:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
PULL_TIMEOUT="${PULL_TIMEOUT:-300}"

if [[ -n "${GHCR_USER}" && -n "${GHCR_TOKEN}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
fi

if command -v timeout >/dev/null 2>&1; then
  timeout "${PULL_TIMEOUT}" docker pull "${IMAGE_NAME}"
else
  docker pull "${IMAGE_NAME}"
fi
