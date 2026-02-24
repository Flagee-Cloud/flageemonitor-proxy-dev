#!/usr/bin/env bash
#
# zbx_ssh_test.sh
# Testa autenticação SSH a partir de um JSON passado pelo Zabbix {MANUALINPUT}.
#
# Formato de entrada (string):
#   {"u":"root","p":"SuP3r$3nh@!","h":"192.168.1.4","P":22}
#
# Campos:
#   u  → usuário   (obrigatório)
#   p  → senha     (obrigatório)
#   h  → host/IP   (obrigatório)
#   P  → porta SSH (opcional; padrão 22)
#
# Saída:
#   STDOUT – “OK: …”  (exit 0)
#   STDERR – “FALHA: …” (exit ≠ 0)

set -euo pipefail

INPUT="${1-}"

if [[ -z "$INPUT" ]]; then
  echo "FALHA: nenhum parâmetro recebido. Esperava JSON." >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# 1) Faz o parse do JSON
#    Tenta primeiro 'jq'.  Se não existir, usa Python 3 (geralmente presente).
# ---------------------------------------------------------------------------
json_get() {
  local key=$1
  if command -v jq >/dev/null 2>&1; then
    echo "$INPUT" | jq -r --arg k "$key" '.[$k] // empty'
  else
    # Python embutido para evitar dependência externa
    python3 - <<'PY' "$INPUT" "$key"
import json, sys, html
data = json.loads(sys.argv[1])
print(data.get(sys.argv[2], ''), end='')
PY
  fi
}

ZUSER=$(json_get u)
ZPASS=$(json_get p)
ZHOST=$(json_get h)
ZPORT=$(json_get P)

# Valores padrão / validações simples
: "${ZPORT:=22}"

if [[ -z "$ZUSER" || -z "$ZPASS" || -z "$ZHOST" ]]; then
  echo "FALHA: JSON deve conter chaves 'u','p','h' (e opcional 'P')." >&2
  exit 3
fi

# ---------------------------------------------------------------------------
# 2) Executa o teste SSH
# ---------------------------------------------------------------------------

TIMEOUT=30

if timeout "$TIMEOUT" sshpass -p "$ZPASS" \
    ssh -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o HostKeyAlgorithms=+ssh-dss \
        -p "$ZPORT" \
        "$ZUSER@$ZHOST" \
        'exit 0' >/dev/null 2>&1
then
  echo "OK: Autenticado com sucesso em $ZHOST:$ZPORT como $ZUSER."
  exit 0
else
  RC=$?
  case $RC in
    5)  echo "FALHA: senha incorreta (ou root desabilitado)." >&2 ;;
    6)  echo "FALHA: chave do host desconhecida." >&2 ;;
    124) echo "FALHA: timeout de ${TIMEOUT}s." >&2 ;;
    255) echo "FALHA: host inacessível ou conexão rejeitada." >&2 ;;
    *)  echo "FALHA: erro desconhecido (código $RC)." >&2 ;;
  esac
  exit $RC
fi
