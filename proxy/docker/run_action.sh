#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: run_action.sh <acao> [args]"
  exit 1
fi

if [[ ! -f /ariusmonitor/config_bot.json ]]; then
  /ariusmonitor/update_config.sh || true
fi

if [[ ! -f /ariusmonitor/config_bot.json ]]; then
  echo "ERRO: Arquivo de configuracao '/ariusmonitor/config_bot.json' nao encontrado."
  exit 1
fi

exec /usr/local/bin/python3 /ariusmonitor/runtime/main.py "$@"
