#!/usr/bin/env bash

# Uso: ./teste_mtu_latency.sh <host> [max_size] [min_size] [step] [count] [timeout]
# Exemplo: ./teste_mtu_latency.sh example.com 1472 1400 10 5 1

# Cores ANSI
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
BOLD='\033[1m'
RESET='\033[0m'

HOST="$1"
MAX_SIZE=${2:-1472}
MIN_SIZE=${3:-1400}
STEP=${4:-10}
COUNT=${5:-5}
TIMEOUT=${6:-1}

if [[ -z "$HOST" ]]; then
  echo -e "${RED}Erro:${RESET} informe o host de destino."
  echo "Exemplo: $0 example.com"
  exit 1
fi

echo -e "${BOLD}${CYAN}==> Teste de MTU para $HOST${RESET}"
mtu_payload=0
size=$MAX_SIZE

while (( size >= MIN_SIZE )); do
  echo -en "${YELLOW}Testando payload $size...${RESET} "
  if ping -c1 -M do -s $size -W $TIMEOUT $HOST &>/dev/null; then
    echo -e "${GREEN}✓ Sucesso${RESET}"
    mtu_payload=$size
    break
  else
    echo -e "${RED}✗ Falhou${RESET}"
  fi
  size=$((size - STEP))
done

if (( mtu_payload > 0 )); then
  mtu=$((mtu_payload + 28))
  echo -e "${GREEN}  MTU máxima suportada: $mtu bytes (payload = $mtu_payload)${RESET}"
else
  echo -e "${RED}  Não foi possível determinar o MTU entre $MIN_SIZE e $MAX_SIZE.${RESET}"
fi

echo
echo -e "${BOLD}${CYAN}==> Teste de latência para $HOST (usando $COUNT pacotes)${RESET}"
TMPFILE=$(mktemp)
ping -c $COUNT $HOST > "$TMPFILE" 2>/dev/null

if grep -qE 'min/avg/max' "$TMPFILE"; then
  stats=$(grep -P 'min/avg/max' "$TMPFILE" | awk -F' = ' '{print $2}')
  stats=${stats% ms}
  IFS='/' read -r min avg max mdev <<< "$stats"
  echo -e "${BOLD}  Latência (ms):${RESET}"
  echo -e "    • Mínimo : ${GREEN}$min${RESET}"
  echo -e "    • Média  : ${YELLOW}$avg${RESET}"
  echo -e "    • Máximo : ${RED}$max${RESET}"
  echo -e "    • Desvio : ${CYAN}$mdev${RESET}"
else
  echo -e "${RED}  Falha ao obter estatísticas de latência.${RESET}"
fi

rm -f "$TMPFILE"
