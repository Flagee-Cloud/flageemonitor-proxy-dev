#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_promocao.lock"
DB_NAME="controle"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log_promocao.txt"
>$LOG_FILE

# Parâmetros de data
dtini="$1"
dtfim="$2"

# Função para enviar traps para o Zabbix
send_zabbix_trap() {
    local status="$1"
    local message="$2"
    local zbx_sender_server="${PARAM_ZABBIX_SENDER_SERVER:-127.0.0.1}"
    local zbx_sender_port="${PARAM_ZABBIX_SENDER_PORT:-10051}"
    zabbix_sender -z "$zbx_sender_server" -p "$zbx_sender_port" -s "$PARAM_REDE-PROXY" -k "promocao.mysql.conexao" -o "{\"status\":\"$status\", \"message\":\"$message\"}"
}

# Verificar se o script já está em execução
if [ -f "$LOCK_FILE" ]; then
    echo "Script já está em execução." | tee -a "$LOG_FILE"
    exit 1
else
    touch "$LOCK_FILE"
    trap "rm -f $LOCK_FILE" EXIT
fi

# Definir a consulta SQL com base nos parâmetros fornecidos
if [ -z "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho, CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido, vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha FROM promocaodesconto WHERE DataFim >= NOW();"
elif [ -n "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho, CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido, vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha FROM promocaodesconto WHERE DataFim >= '$dtini';"
elif [ -n "$dtini" ] && [ -n "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho, CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido, vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha FROM promocaodesconto WHERE DataFim BETWEEN '$dtini' AND '$dtfim';"
fi

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE

    RESULTS=$(timeout 120 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names)
    ERRO=$?

    if [ $ERRO -eq 124 ]; then
        echo "Timeout" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "PROMOCAO - Timeout ao conectar no MySQL em $DB_HOST"
        continue
    elif [[ $RESULTS == *"ERROR"* ]]; then
        echo "Erro de conexão ou consulta: $RESULTS" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "PROMOCAO - Erro ao conectar no MySQL em $DB_HOST"
        continue
    elif [ -z "$RESULTS" ]; then
        echo "Nenhum resultado da consulta em $DB_HOST." | tee -a $LOG_FILE
        continue
    fi

    send_zabbix_trap "sucesso" "PROMOCAO - Conectado com sucesso no MySQL em $DB_HOST"

    echo "Processando resultados da consulta em $DB_HOST" | tee -a $LOG_FILE
    contador=0
    lote_sql="INSERT INTO mercador_promocao (empresa_id, loja_codigo, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho, CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido, vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha) VALUES "
    last_loja=""

    while IFS=$'\t' read -r nroloja CodPromocao Descricao TipoPromocao CodGrpGatilho QtdGatilho CodGrpDesc QtdDesc PercDesc DataInicio DataFim DataExclusao Excluido vinculadoMeioPagto TipoDesconto ExcluiOferta nome_campanha; do
        last_loja=$nroloja
        lote_sql="${lote_sql}('$PARAM_EMPRESA_ID', '$nroloja', '$CodPromocao', '$Descricao', '$TipoPromocao', '$CodGrpGatilho', '$QtdGatilho', '$CodGrpDesc', '$QtdDesc', '$PercDesc', '$DataInicio', '$DataFim', '$DataExclusao', '$Excluido', '$vinculadoMeioPagto', '$TipoDesconto', '$ExcluiOferta', '$nome_campanha'), "

        ((contador++))

        if [ "$contador" -eq 500 ]; then
            lote_sql=${lote_sql%, }
            lote_sql="$lote_sql ON DUPLICATE KEY UPDATE Descricao=VALUES(Descricao), CodGrpGatilho=VALUES(CodGrpGatilho), QtdGatilho=VALUES(QtdGatilho), CodGrpDesc=VALUES(CodGrpDesc), QtdDesc=VALUES(QtdDesc), PercDesc=VALUES(PercDesc), DataInicio=VALUES(DataInicio), DataFim=VALUES(DataFim), DataExclusao=VALUES(DataExclusao), Excluido=VALUES(Excluido), vinculadoMeioPagto=VALUES(vinculadoMeioPagto), TipoDesconto=VALUES(TipoDesconto), ExcluiOferta=VALUES(ExcluiOferta), nome_campanha=VALUES(nome_campanha);"

            echo "Enviando lote de 500 registros para o BI..." | tee -a $LOG_FILE
            
            INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
            if [ $? -ne 0 ]; then
                echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
            else
                echo "Lote 500 enviado com sucesso para LOJA: $last_loja" | tee -a $LOG_FILE
            fi
            contador=0
            lote_sql="INSERT INTO mercador_promocao (empresa_id, loja_codigo, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho, CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido, vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha) VALUES "
        fi
    done <<< "$RESULTS"

    if [ "$contador" -gt 0 ]; then
        lote_sql=${lote_sql%, }
        lote_sql="$lote_sql ON DUPLICATE KEY UPDATE Descricao=VALUES(Descricao), CodGrpGatilho=VALUES(CodGrpGatilho), QtdGatilho=VALUES(QtdGatilho), CodGrpDesc=VALUES(CodGrpDesc), QtdDesc=VALUES(QtdDesc), PercDesc=VALUES(PercDesc), DataInicio=VALUES(DataInicio), DataFim=VALUES(DataFim), DataExclusao=VALUES(DataExclusao), Excluido=VALUES(Excluido), vinculadoMeioPagto=VALUES(vinculadoMeioPagto), TipoDesconto=VALUES(TipoDesconto), ExcluiOferta=VALUES(ExcluiOferta), nome_campanha=VALUES(nome_campanha);"

        echo "Enviando lote final de $contador registros para o BI..." | tee -a $LOG_FILE

        INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
        else
            echo "Lote final de $contador enviado com sucesso para LOJA: $last_loja" | tee -a $LOG_FILE
        fi
    fi
done

rm -f "$LOCK_FILE"
