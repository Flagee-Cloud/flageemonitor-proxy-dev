#!/bin/bash

source /ariusmonitor/config_bot.conf

# Função para enviar traps para o Zabbix
send_zabbix_trap() {
    local status="$1"
    local message="$2"
    zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s "$PARAM_REDE-PROXY" -k "concentrador.mysql.conexao" -o "{\"status\":\"$status\", \"message\":\"$message\"}"
}

DB_USER="htc"
DB_NAME="controle"
# DB_PASS="htc_password_Harpo2021"

SQL_QUERY="SELECT sat_fabricante, sat_senha, nroloja, codigo, ip FROM pf_pdv order by codigo"

JSON_GET_GROUPID='{
    "jsonrpc": "2.0",
    "method": "hostgroup.get",
    "params": {
        "output": ["groupid"],
        "filter": {
            "name": ["'$PARAM_REDE'"]
        }
    },
    "id": 1
}'

log_with_timestamp() {
    local message=$1
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" | tee -a "$2"
}

# --- Consultar GroupID com log detalhado ---

log_with_timestamp "Consultando o grupo '$PARAM_REDE' no Zabbix..." "$PARAM_BASE_DIR/log_connect_debug.log"

GROUP_RESPONSE=$(curl -k -s -X POST -H 'Content-Type: application/json' -H "Authorization: Bearer $PARAM_TOKEN" -d "$JSON_GET_GROUPID" https://$PARAM_ZABBIX_SERVER/api_jsonrpc.php)

log_with_timestamp "Resposta da API ao consultar grupo: $GROUP_RESPONSE" "$PARAM_BASE_DIR/log_connect_debug.log"

GROUPID=$(echo $GROUP_RESPONSE | jq -r '.result[0].groupid')

if [[ -z "$GROUPID" || "$GROUPID" == "null" ]]; then
    ERROR_MESSAGE=$(echo $GROUP_RESPONSE | jq -r '.error | @json')
    if [[ "$ERROR_MESSAGE" != "null" ]]; then
        log_with_timestamp "Erro retornado pela API: $ERROR_MESSAGE" "$PARAM_BASE_DIR/log_connect_error.log"
    fi
    log_with_timestamp "Nenhum grupo encontrado com o nome '$PARAM_REDE'. Conferir se a autenticação e o nome do grupo estão corretos." "$PARAM_BASE_DIR/log_connect_notfound.log"
    exit 1
fi

log_with_timestamp "Grupo '$PARAM_REDE' encontrado com ID $GROUPID." "$PARAM_BASE_DIR/log_connect_debug.log"


for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    # Execute a consulta e leia os resultados diretamente, suprimindo o aviso de senha
    RESULTS=$(timeout 60 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$SQL_QUERY" -B -N)
    ERRO=$?

    if [ $ERRO -eq 124 ]; then
        log_with_timestamp "Timeout" "$PARAM_BASE_DIR/log_connect_error.log"
        send_zabbix_trap "erro" "SAT CONF -  - Timeout ao conectar no MySQL em $DB_HOST"
        continue
    elif [[ $RESULTS == *"ERROR"* ]]; then
        log_with_timestamp "Erro de conexão ou consulta: $RESULTS" "$PARAM_BASE_DIR/log_connect_error.log"
        send_zabbix_trap "erro" "SAT CONF -  - Erro de conexão ou consulta ao MySQL em $DB_HOST: $RESULTS"
        continue
    elif [ -z "$RESULTS" ]; then
        log_with_timestamp "Nenhum resultado da consulta em $DB_HOST." "$PARAM_BASE_DIR/log_connect_error.log"
        # send_zabbix_trap "erro" "SAT CONF -  - Nenhum resultado da consulta ao MySQL em $DB_HOST."
        continue
    else
        log_with_timestamp "Conectando ao IP $DB_HOST" /dev/null
        send_zabbix_trap "sucesso" "SAT CONF - Conexão bem-sucedida ao MySQL em $DB_HOST."
    fi

    echo "$RESULTS" | while IFS=$'\t' read -r sat_fabricante sat_senha nroloja codigo ip
    do
        nroloja=$(printf "%03d" $nroloja)

        JSON_GET_HOSTID='{
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": "extend",
                "selectMacros": "extend",
                "selectInterfaces": ["ip"],
                "groupids": ["'$GROUPID'"],
                "filter": {
                    "ip": ["'$ip'"]
                }
            },
            "id": 1
        }'

        RESPONSE=$(curl -k -s -X POST -H 'Content-Type: application/json' -H "Authorization: Bearer $PARAM_TOKEN" -d "$JSON_GET_HOSTID" https://$PARAM_ZABBIX_SERVER/api_jsonrpc.php)
        HOSTID=$(echo $RESPONSE | jq -r '.result[0].hostid')
        MACROS=$(echo $RESPONSE | jq '.result[0].macros')

        if [[ -z "$HOSTID" || "$HOSTID" == "null" ]]; then
            log_with_timestamp "Host não encontrado: LOJA $nroloja PDV $codigo IP $ip SAT $sat_fabricante" "$PARAM_BASE_DIR/log_connect_notfound.log"
            continue
        fi

        NEED_UPDATE=false

        update_macro() {
            local macro_name="$1"
            local macro_value="$2"
            local existing_macro

            existing_macro=$(echo "$MACROS" | jq --arg macro "$macro_name" '.[] | select(.macro == $macro)')
            if [[ -n "$existing_macro" ]]; then
                local existing_value
                existing_value=$(echo "$existing_macro" | jq -r '.value')
                if [[ "$existing_value" != "$macro_value" ]]; then
                    NEED_UPDATE=true
                    MACROS=$(echo "$MACROS" | jq --arg macro "$macro_name" --arg value "$macro_value" 'map(if .macro == $macro then .value = $value else . end)')
                fi
            else
                NEED_UPDATE=true
                local new_macro
                new_macro=$(jq -n --arg macro "$macro_name" --arg value "$macro_value" '{macro: $macro, value: $value}')
                MACROS=$(echo "$MACROS" | jq --argjson newMacro "$new_macro" '. + [$newMacro]')
            fi
        }

        update_macro '{$SAT_FABRICANTE}' "$sat_fabricante"
        update_macro '{$SAT_SENHA}' "$sat_senha"

        if $NEED_UPDATE; then
            CLEAN_MACROS=$(echo "$MACROS" | jq 'map({macro: .macro, value: .value})' | jq -c)

            JSON_UPDATE_HOST=$(jq -n --argjson macros "$CLEAN_MACROS" --arg hostid "$HOSTID" --arg auth "$PARAM_TOKEN" '{
                "jsonrpc": "2.0",
                "method": "host.update",
                "params": {
                    "hostid": $hostid,
                    "macros": $macros
                },
                "id": 1
            }')

            FINAL_RESPONSE=$(curl -k -s -X POST -H 'Content-Type: application/json' -H "Authorization: Bearer $PARAM_TOKEN" -d "$JSON_UPDATE_HOST" https://$PARAM_ZABBIX_SERVER/api_jsonrpc.php)
            if echo $FINAL_RESPONSE | jq -e '.error' >/dev/null; then
                log_with_timestamp "Erro ao atualizar: LOJA $nroloja PDV $codigo IP $ip." "$PARAM_BASE_DIR/log_connect_error.log"
                log_with_timestamp "$FINAL_RESPONSE" "$PARAM_BASE_DIR/log_connect_error.log"
            else
                log_with_timestamp "Atualizado: LOJA $nroloja PDV $codigo IP $ip SAT $sat_fabricante" "$PARAM_BASE_DIR/log_connect_atualizado.log"
            fi
        else
            log_with_timestamp "Não é necessário atualizar: LOJA $nroloja PDV $codigo IP $ip SAT $sat_fabricante" "$PARAM_BASE_DIR/log_connect_naoatualizado.log"
        fi
    done
done
