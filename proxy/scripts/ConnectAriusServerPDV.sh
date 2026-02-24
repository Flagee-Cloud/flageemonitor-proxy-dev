#!/bin/bash
set -euo pipefail

source /ariusmonitor/config_bot.conf

ZBX_URL='https://monitor.flagee.cloud/api_jsonrpc.php'

# Função para enviar traps para o Zabbix
send_zabbix_trap() {
  local status="$1"
  local message="$2"
  zabbix_sender -c /etc/zabbix/zabbix_agentd.conf \
    -s "${PARAM_REDE}-PROXY" \
    -k "concentrador.mysql.conexao" \
    -o "{\"status\":\"$status\", \"message\":\"$message\"}"
}

DB_USER="$DB_USER"
DB_NAME="controle"
DB_PASS="$DB_PASS"
NRO_LOJA=""

# Tratamento de parâmetros
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --loja) NRO_LOJA="$2"; shift 2 ;;
    *) echo "Uso: $0 [--loja <nroloja>]"; exit 1 ;;
  esac
done

# Monta a consulta SQL
if [[ -n "$NRO_LOJA" ]]; then
  SQL_QUERY="SELECT sat_fabricante, nroloja, codigo, ip FROM pf_pdv WHERE nroloja = '$NRO_LOJA'"
else
  SQL_QUERY="SELECT sat_fabricante, nroloja, codigo, ip FROM pf_pdv"
fi

# ===== hostgroup.get =====
JSON_GET_GROUPID=$(jq -n --arg name "$PARAM_REDE" '{
  "jsonrpc":"2.0",
  "method":"hostgroup.get",
  "params":{
    "output":["groupid"],
    "filter":{"name":[ $name ]}
  },
  "id":1
}')

GROUP_RESPONSE=$(curl -k -sS -X POST \
  -H "Content-Type: application/json-rpc" \
  -H "Authorization: Bearer $PARAM_TOKEN" \
  -d "$JSON_GET_GROUPID" "$ZBX_URL")

GROUPID=$(echo "$GROUP_RESPONSE" | jq -r '.result[0].groupid // empty')

if [[ -z "$GROUPID" ]]; then
  echo "Nenhum grupo encontrado com o nome $PARAM_REDE."
  echo "Resposta: $GROUP_RESPONSE"
  exit 1
fi

# (Zabbix 7) Para host ser monitorado por proxy:
# monitored_by=1 e proxyid=<ID do proxy>  :contentReference[oaicite:1]{index=1}
PROXYID="${PARAM_ZABBIX_PROXYID:-}"
if [[ -z "$PROXYID" ]]; then
  echo "PARAM_ZABBIX_PROXYID não definido no config."
  exit 1
fi

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"; do
  echo "Conectando ao IP $DB_HOST"
  RESULTS=$(mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$SQL_QUERY" -B -N || true)

  if [[ -z "$RESULTS" ]]; then
    echo "Nenhum resultado da consulta em $DB_HOST."
    continue
  fi

  echo "$RESULTS" | while IFS=$'\t' read -r sat_fabricante nroloja codigo ip; do
    nroloja=$(printf "%03d" "$nroloja")
    HOST="${PARAM_REDE}-LOJA${nroloja}-PDV${codigo}"
    NAME="${PARAM_REDE} (LOJA${nroloja}) PDV${codigo}"

    JSON_CREATE_HOST=$(jq -n \
      --arg host "$HOST" \
      --arg name "$NAME" \
      --arg ip "$ip" \
      --arg groupid "$GROUPID" \
      --arg sat_fabricante "$sat_fabricante" \
      --argjson proxyid "$PROXYID" \
      '{
        "jsonrpc":"2.0",
        "method":"host.create",
        "params":{
          "host": $host,
          "name": $name,

          "interfaces":[
            {"type":1,"main":1,"useip":1,"ip":$ip,"dns":"","port":"10050"}
          ],

          "groups":[{"groupid": $groupid}],

          "tags":[
            {"tag":"PDV_TIPO","value":"PDV_PADRAO"}
          ],

          "templates":[
            {"templateid":"10543"},
            {"templateid":"10552"}
          ],

          "macros":[
            {"macro":"{$DDMM}","value":"0405"},
            {"macro":"{$HORARIOCOMERCIAL}","value":"1"},
            {"macro":"{$MONITORA_ARQUIVO_CARGA}","value":"1","description":"Bool"},
            {"macro":"{$MONITORA_BALANCA}","value":"1","description":"Bool"},
            {"macro":"{$MONITORA_PINPAD}","value":"1","description":"Bool"},
            {"macro":"{$SAT_FABRICANTE}","value": $sat_fabricante}
          ],

          "inventory_mode": 1,
          "inventory": {
            "notes": "root,123456"
          },

          "monitored_by": 1,
          "proxyid": $proxyid
        },
        "id":1
      }')

    FINAL_RESPONSE=$(curl -k -sS -X POST \
      -H "Content-Type: application/json-rpc" \
      -H "Authorization: Bearer $PARAM_TOKEN" \
      -d "$JSON_CREATE_HOST" "$ZBX_URL")

    if echo "$FINAL_RESPONSE" | jq -e '.error' >/dev/null; then
      echo "Erro ao criar host: LOJA $nroloja PDV $codigo IP $ip SAT $sat_fabricante"
      echo "RESPOSTA: $FINAL_RESPONSE"
      echo ""
    else
      echo "Criado: LOJA $nroloja PDV $codigo IP $ip SAT $sat_fabricante"
    fi
  done
done
