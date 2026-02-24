#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: run_action.sh <acao> [args]"
  exit 1
fi

if [[ ! -f /flageemonitor/config_bot.json ]]; then
  /flageemonitor/update_config.sh || true
fi

if [[ ! -f /flageemonitor/config_bot.json ]]; then
  echo "ERRO: Arquivo de configuracao '/flageemonitor/config_bot.json' nao encontrado."
  exit 1
fi

exec /usr/local/bin/python3 /flageemonitor/runtime/main.py "$@"
