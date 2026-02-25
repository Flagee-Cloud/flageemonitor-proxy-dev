#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_cupom.lock"
DB_NAME="retag"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log_cupom.txt"
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
    zabbix_sender -z "$zbx_sender_server" -p "$zbx_sender_port" -s "$PARAM_REDE-PROXY" -k "concentrador.mysql.conexao" -o "{\"status\":\"$status\", \"message\":\"$message\"}"
}

# Verificar se o script já está em execução
if [ -f "$LOCK_FILE" ]; then
    echo "Script já está em execução." | tee -a "$LOG_FILE"
    exit 1
else
    # Cria o arquivo de bloqueio para indicar que este processo está em execução
    touch "$LOCK_FILE"
    # Garante que o arquivo de bloqueio será removido ao sair do script, mesmo após uma interrupção
    trap "rm -f $LOCK_FILE" EXIT
fi

# Definir a consulta SQL com base nos parâmetros fornecidos
if [ -z "$dtini" ] && [ -z "$dtfim" ]; then
    #SQL_QUERY="SELECT DataProc FROM cupom WHERE HoraMinSeg >= DATE_SUB(NOW(), INTERVAL 10 MINUTE);"
    SQL_QUERY="SELECT DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao, total, FlagInicupom, FlagFimCupom FROM cupom WHERE DataProc >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND DataProc <= DATE_SUB(NOW(), INTERVAL 1 DAY);"
elif [ -n "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao, total, FlagInicupom, FlagFimCupom FROM cupom WHERE HoraMinSeg >= '$dtini' AND HoraMinSeg <= DATE_SUB(NOW(), INTERVAL 1 HOUR);"
elif [ -n "$dtini" ] && [ -n "$dtfim" ]; then
    SQL_QUERY="SELECT DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao, total, FlagInicupom, FlagFimCupom FROM cupom WHERE HoraMinSeg BETWEEN '$dtini' AND '$dtfim';"
fi

#echo $SQL_QUERY | tee -a $LOG_FILE

# PARAM_IP_CONCENTRADORES=("172.22.3.130")

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE

    # Execute a consulta e leia os resultados diretamente, suprimindo o aviso de senha
    RESULTS=$(timeout 120 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names)
    #echo $RESULTS
    ERRO=$?

    if [ $ERRO -eq 124 ]; then
        echo "Timeout" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "CUPOM -  - Timeout ao conectar no MySQL em $DB_HOST"
        continue
    elif [[ $RESULTS == *"ERROR"* ]]; then
        echo "Erro de conexão ou consulta: $RESULTS" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "CUPOM -  - Erro ao conectar no MySQL em $DB_HOST"
        continue
    elif [ -z "$RESULTS" ]; then
        echo "Nenhum resultado da consulta em $DB_HOST." | tee -a $LOG_FILE
        continue
    fi

    send_zabbix_trap "sucesso" "CUPOM - Conectado com sucesso no MySQL em $DB_HOST"

    # Processa os resultados
    echo "Processando resultados da consulta em $DB_HOST" | tee -a $LOG_FILE
    contador=0
    lote_sql="INSERT INTO cupom (rede, DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao, total, FlagInicupom, FlagFimCupom) VALUES "
    last_nroloja=""

    while IFS=$'\t' read -r DataProc nroloja NroCupom Pdv HoraMinSeg NroItens FlagEstorno LV tipooperacao total FlagInicupom FlagFimCupom; do
    #while IFS=$'\t' read -r DataProc; do
        

        #echo "PARAM_REDE='$PARAM_REDE', DataProc='$DataProc', nroloja='$nroloja', NroCupom='$NroCupom', Pdv='$Pdv', HoraMinSeg='$HoraMinSeg', NroItens='$NroItens', FlagEstorno='$FlagEstorno', LV='$LV', tipooperacao='$tipooperacao', total='$total', FlagInicupom='$FlagInicupom', FlagFimCupom='$FlagFimCupom'" | tee -a $LOG_FILE

        # Montar a query do lote
        last_nroloja=$nroloja
        lote_sql="${lote_sql}('$PARAM_REDE', '$DataProc', '$nroloja', '$NroCupom', '$Pdv', '$HoraMinSeg', '$NroItens', '$FlagEstorno', '$LV', '$tipooperacao', '$total', '$FlagInicupom', '$FlagFimCupom'), "

        ((contador++))

        # Enviar lote a cada 500 registros
        if [ "$contador" -eq 500 ]; then
            lote_sql=${lote_sql%, }
            lote_sql="$lote_sql ON DUPLICATE KEY UPDATE HoraMinSeg=VALUES(HoraMinSeg), NroItens=VALUES(NroItens), DataProc=VALUES(DataProc), LV=VALUES(LV), tipooperacao=VALUES(tipooperacao), total=VALUES(total), FlagInicupom=VALUES(FlagInicupom), FlagFimCupom=VALUES(FlagFimCupom);"

            echo "Enviando lote de 500 registros para o BI..." | tee -a $LOG_FILE
            
            INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
            if [ $? -ne 0 ]; then
                echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
            else
                echo "Lote 500 enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
            fi
            contador=0
            lote_sql="INSERT INTO cupom (rede, DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao, total, FlagInicupom, FlagFimCupom) VALUES "
        fi
    done <<< "$RESULTS"

    # Enviar o lote final
    if [ "$contador" -gt 0 ]; then
        lote_sql=${lote_sql%, }
        lote_sql="$lote_sql ON DUPLICATE KEY UPDATE HoraMinSeg=VALUES(HoraMinSeg), NroItens=VALUES(NroItens), DataProc=VALUES(DataProc), LV=VALUES(LV), tipooperacao=VALUES(tipooperacao), total=VALUES(total), FlagInicupom=VALUES(FlagInicupom), FlagFimCupom=VALUES(FlagFimCupom);"

        echo "Enviando lote final de $contador registros para o BIVarejo..." | tee -a $LOG_FILE

        INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados no banco BIVarejo: $INSERT_ERROR" | tee -a $LOG_FILE
        else
            echo "Lote final de $contador enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
        fi
    fi
    
    echo ""
    echo ""
done

# Lembre-se de remover o arquivo de lock no final do script
rm -f "$LOCK_FILE"
