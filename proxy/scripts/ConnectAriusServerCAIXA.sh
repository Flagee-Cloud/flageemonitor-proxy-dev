#!/bin/bash
# Envia operador_id via zabbix_sender (usando -c /etc/zabbix/zabbix_agentd.conf)
# Hostname no formato: REDE-LOJA%03d-PDV%03d (ex.: MLAR-LOJA045-PDV213)

set -Eeuo pipefail

##### AMBIENTE SEGURO PARA CRON #####
# PATH mínimo completo (cron costuma vir bem pelado)
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Opcional: locale (evita frescura de charset em alguns ambientes)
export LANG="pt_BR.UTF-8"
export LC_ALL="pt_BR.UTF-8"

# Opcional: log básico de debug quando rodar via cron
LOG_DIR="/ariusmonitor/logs"
mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/enviar_operador_id.log" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando $(basename "$0") (PID $$)"

##### FIM AMBIENTE #####

# Cores (se quiser pode manter, no log vai ver os códigos)
RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'

# Verbosidade opcional (export DEBUG=1 para habilitar -vv no sender)
DEBUG="${DEBUG:-0}"

# --- Controle de concorrência com flock ---
LOCK_FILE="/run/lock/ConnectAriusServerCAIXA.lock"
MAX_AGE_SECONDS=$((60 * 60))  # 1 hora

# Se o lock existe, verificar se é “velho demais”
if [[ -e "$LOCK_FILE" ]]; then
  now_ts=$(date +%s)
  lock_ts=$(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo "$now_ts")

  age=$(( now_ts - lock_ts ))
  if (( age > MAX_AGE_SECONDS )); then
    echo -e "${RED}[LOCK] Lock antigo detectado (>${MAX_AGE_SECONDS}s). Removendo: $LOCK_FILE${NC}"
    rm -f "$LOCK_FILE" || echo -e "${RED}[LOCK] Falha ao remover lock antigo${NC}"
  fi
fi

# Abre FD associado ao arquivo de lock
exec {LOCK_FD}>"$LOCK_FILE" || {
  echo -e "${RED}[LOCK] Não foi possível abrir o arquivo de lock: $LOCK_FILE${NC}"
  exit 1
}

# Tenta obter o lock sem bloquear (-n)
if ! flock -n "$LOCK_FD"; then
  echo -e "${RED}Outra instância de $(basename "$0") já está em execução. Abortando.${NC}"
  exit 1
fi

# Opcional: escrever algo no lock (PID, timestamp) para debug
echo "$$ $(date '+%Y-%m-%d %H:%M:%S')" >&"$LOCK_FD"
# --- Fim do controle de concorrência ---

# Configurações externas esperadas:
CONF="/ariusmonitor/config_bot.conf"
if [[ ! -r "$CONF" ]]; then
  echo -e "${RED}Arquivo de configuração não encontrado: $CONF${NC}"
  exit 1
fi

# shellcheck source=/dev/null
source "$CONF"

# Resolve caminhos dos binários (caso o PATH ainda não ajude)
PSQL_BIN="$(command -v psql || echo /usr/bin/psql)"
ZABBIX_SENDER_BIN="$(command -v zabbix_sender || echo /usr/bin/zabbix_sender)"

echo "Usando psql em: $PSQL_BIN"
echo "Usando zabbix_sender em: $ZABBIX_SENDER_BIN"

# Configuração do Zabbix (usa o proxy/endereço do agent local)
ZABBIX_CONFIG="/etc/zabbix/zabbix_agentd.conf"
ZABBIX_KEY="pdv.neo.operador_id"

# Hosts remotos para consulta
REMOTE_HOSTS=("${PARAM_IP_CONCENTRADORES[@]}")

# Query (saída compacta com separador |)
QUERY="
SELECT l.codigo AS codigo_loja,
       p.codigo AS codigo_pdv,
       b.operadorid
FROM pdvvalor b
JOIN pdv p   ON p.id = b.pdvid
JOIN loja l  ON l.id = p.lojaid
WHERE b.tipo = 5
  AND (b.pdvid, b.coo) IN (
    SELECT a.pdvid, MAX(a.coo)
    FROM pdvvalor a
    WHERE a.tipo = 5
    GROUP BY a.pdvid
  )
ORDER BY l.codigo, p.codigo;
"

for HOST in "${REMOTE_HOSTS[@]}"; do
  echo "Conectando ao host remoto: $HOST"

  RESULT=$(PGPASSWORD="$DB_PG_PASS" \
           "$PSQL_BIN" -h "$HOST" -U "$DB_PG_USER" -d "$DB_PG_DB" -p "$DB_PG_PORT" \
           -t -A -F '|' -c "$QUERY" 2>&1) || true

  if [[ -z "$RESULT" ]]; then
    echo -e "${RED}Sem resultados (ou erro) no host $HOST. Saída do psql:${NC}"
    echo "$RESULT"
    continue
  fi

  while IFS='|' read -r codigo_loja codigo_pdv operadorid; do
    [[ -z "$codigo_loja" ]] && continue

    codigo_loja=$(echo "$codigo_loja" | xargs)
    codigo_pdv=$(echo "$codigo_pdv" | xargs)
    operadorid=$(echo "$operadorid" | xargs)

    if ! [[ "$codigo_loja" =~ ^[0-9]+$ && "$codigo_pdv" =~ ^[0-9]+$ ]]; then
      echo -e "${RED}Linha inválida: loja='${codigo_loja}' pdv='${codigo_pdv}' op='${operadorid}'${NC}"
      continue
    fi

    loja_pad=$(printf "%03d" "$codigo_loja")
    pdv_pad=$(printf "%03d" "$codigo_pdv")

    HOST_NAME="${PARAM_REDE}-LOJA${loja_pad}-PDV${pdv_pad}"

    cmd=( "$ZABBIX_SENDER_BIN" -c "$ZABBIX_CONFIG" -s "$HOST_NAME" -k "$ZABBIX_KEY" -o "$operadorid" )
    (( DEBUG > 0 )) && cmd+=( -vv )

    if "${cmd[@]}" 1>/tmp/zs.out 2>&1; then
      echo -e "${GREEN}Enviado com sucesso para ${HOST_NAME}: operador_id=${operadorid}${NC}"
    else
      echo -e "${RED}Erro ao enviar para ${HOST_NAME}: operador_id=${operadorid}${NC}"
      sed -n '1,120p' /tmp/zs.out
    fi
    echo
  done <<< "$RESULT"
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fim de $(basename "$0")"
