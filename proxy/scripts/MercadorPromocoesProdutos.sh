#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_promocao_produtos.lock"
DB_NAME="controle"      # Banco remoto onde está a tabela promocaodesconto_grupo

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/script_log_promocao_produtos.txt"
> "$LOG_FILE"

send_zabbix_trap() {
    local status="$1"
    local message="$2"
    local zbx_sender_server="${PARAM_ZABBIX_SENDER_SERVER:-127.0.0.1}"
    local zbx_sender_port="${PARAM_ZABBIX_SENDER_PORT:-10051}"
    zabbix_sender -z "$zbx_sender_server" -p "$zbx_sender_port" -s "$PARAM_REDE-PROXY" -k "promocao.mysql.conexao" -o "{\"status\":\"$status\", \"message\":\"$message\"}"
}

# Verificar execução concorrente
if [ -f "$LOCK_FILE" ]; then
    echo "Script já está em execução." | tee -a "$LOG_FILE"
    exit 1
else
    touch "$LOCK_FILE"
    trap "rm -f $LOCK_FILE" EXIT
fi

# SQL para buscar dados da tabela 'promocaodesconto_grupo'
SQL_QUERY="SELECT nroloja, codigoean, CodGrpMerc 
           FROM promocaodesconto_grupo;"

# Loop para acessar os hosts remotos
for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    echo "Conectando ao IP $DB_HOST" | tee -a "$LOG_FILE"

    # Coletar dados do banco remoto
    RESULTS=$(timeout 120 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names)
    ERRO=$?

    if [ $ERRO -eq 124 ]; then
        echo "Timeout na conexão com $DB_HOST" | tee -a "$LOG_FILE"
        send_zabbix_trap "erro" "PROMOCAO - Timeout ao conectar no MySQL em $DB_HOST"
        continue
    elif [[ $RESULTS == *"ERROR"* ]]; then
        echo "Erro na consulta: $RESULTS" | tee -a "$LOG_FILE"
        send_zabbix_trap "erro" "PROMOCAO - Erro ao conectar no MySQL em $DB_HOST"
        continue
    elif [ -z "$RESULTS" ]; then
        echo "Nenhum resultado retornado em $DB_HOST." | tee -a "$LOG_FILE"
        continue
    fi

    send_zabbix_trap "sucesso" "PROMOCAO - Dados coletados com sucesso no MySQL em $DB_HOST"

    # Inserir dados no banco BI local
    echo "Processando dados retornados..." | tee -a "$LOG_FILE"
    INSERT_SQL="INSERT INTO mercador_promocao_produtos (empresa_id, loja_codigo, codigoean, CodGrpMerc) VALUES "
    lote_sql=""
    contador=0

    while IFS=$'\t' read -r nroloja codigoean CodGrpMerc; do
        lote_sql="${lote_sql}('$PARAM_EMPRESA_ID', '$nroloja', '$codigoean', '$CodGrpMerc'), "
        ((contador++))

        # Enviar em lotes de 500 registros
        if [ "$contador" -eq 500 ]; then
            lote_sql=${lote_sql%, }
            lote_sql="$lote_sql ON DUPLICATE KEY UPDATE CodGrpMerc=VALUES(CodGrpMerc);"
            echo "Enviando lote de 500 registros..." | tee -a "$LOG_FILE"
            mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" "$DB_NAME_BI" -e "$INSERT_SQL $lote_sql"
            contador=0
            lote_sql=""
        fi
    done <<< "$RESULTS"

    # Enviar lote final
    if [ -n "$lote_sql" ]; then
        lote_sql=${lote_sql%, }
        lote_sql="$lote_sql ON DUPLICATE KEY UPDATE CodGrpMerc=VALUES(CodGrpMerc);"
        echo "Enviando lote final..." | tee -a "$LOG_FILE"
        mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" "$DB_NAME_BI" -e "$INSERT_SQL $lote_sql"
    fi
done

rm -f "$LOCK_FILE"
