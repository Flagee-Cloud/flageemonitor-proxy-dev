#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script.lock"
DB_NAME="retag"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log.txt"

# Parâmetros de data
dtini="$1"
dtfim="$2"

# Função para enviar traps para o Zabbix
send_zabbix_trap() {
    local status="$1"
    local message="$2"
    zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s "$PARAM_REDE-PROXY" -k "concentrador.mysql.conexao" -o "{\"status\":\"$status\", \"message\":\"$message\"}"
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
    SQL_QUERY="SELECT nfce.nroloja, nfce.dthr_emit_nfe as DataProc, nfce.Pdv, nfce.NroCupom, nfce.estornado, nfce.chave_nfe, nfce.vICMS, nfce.vICMS_ST, nfce.vPIS, nfce.vPIS_ST, nfce.vCOFINS, nfce.vCOFINS_ST, nfce.vFCP, nfce.vFCP_ST, nfce.LV, nfce.Status FROM nfce WHERE nfce.dthr_emit_nfe >= DATE_SUB(NOW(), INTERVAL 10 MINUTE) and nfce.chave_nfe!='';"
elif [ -n "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT nfce.nroloja, nfce.dthr_emit_nfe as DataProc, nfce.Pdv, nfce.NroCupom, nfce.estornado, nfce.chave_nfe, nfce.vICMS, nfce.vICMS_ST, nfce.vPIS, nfce.vPIS_ST, nfce.vCOFINS, nfce.vCOFINS_ST, nfce.vFCP, nfce.vFCP_ST, nfce.LV, nfce.Status FROM nfce WHERE nfce.dthr_emit_nfe >= '$dtini' and nfce.chave_nfe!='';"
elif [ -n "$dtini" ] && [ -n "$dtfim" ]; then
    SQL_QUERY="SELECT nfce.nroloja, nfce.dthr_emit_nfe as DataProc, nfce.Pdv, nfce.NroCupom, nfce.estornado, nfce.chave_nfe, nfce.vICMS, nfce.vICMS_ST, nfce.vPIS, nfce.vPIS_ST, nfce.vCOFINS, nfce.vCOFINS_ST, nfce.vFCP, nfce.vFCP_ST, nfce.LV, nfce.Status FROM nfce WHERE nfce.dthr_emit_nfe BETWEEN '$dtini' AND '$dtfim' and nfce.chave_nfe!='';"
fi

echo $SQL_QUERY | tee -a $LOG_FILE

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE

    # Execute a consulta e leia os resultados diretamente, suprimindo o aviso de senha
    RESULTS=$(timeout 60 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$SQL_QUERY" -B -N)
    ERRO=$?

    if [ $ERRO -eq 124 ]; then
        echo "Timeout" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "NFCE - Timeout ao conectar no MySQL em $DB_HOST"
        continue
    elif [[ $RESULTS == *"ERROR"* ]]; then
        echo "Erro de conexão ou consulta: $RESULTS" | tee -a $LOG_FILE
        send_zabbix_trap "erro" "NFCE - Erro de conexão ou consulta ao MySQL em $DB_HOST: $RESULTS"
        continue
    elif [ -z "$RESULTS" ]; then
        echo "Nenhum resultado da consulta em $DB_HOST." | tee -a $LOG_FILE
        # send_zabbix_trap "erro" "NFCE - Nenhum resultado da consulta ao MySQL em $DB_HOST."
        continue
    else
        echo "Conexão bem-sucedida ao MySQL em $DB_HOST." | tee -a $LOG_FILE
        send_zabbix_trap "sucesso" "NFCE - Conexão bem-sucedida ao MySQL em $DB_HOST."
    fi

    # Processa os resultados
    echo "Processando resultados da consulta em $DB_HOST" | tee -a $LOG_FILE
    contador=0
    lote_sql="INSERT INTO cfe_retorno (rede, nroloja, DataProc, Pdv, Chave, modelo, emServidor, nCupom, vICMS, vICMS_ST, vPIS, vPIS_ST, vCOFINS, vCOFINS_ST, vFCP, vFCP_ST, LV, estornado, dEmi, Status) VALUES "
    last_nroloja=""

    while IFS=$'\t' read -r nroloja DataProc Pdv NroCupom estornado chave_nfe vICMS vICMS_ST vPIS vPIS_ST vCOFINS vCOFINS_ST vFCP vFCP_ST LV
    do
        # Validar o valor de nroloja
        if ! [[ "$nroloja" =~ ^-?[0-9]+$ ]]; then
            echo "Erro: nroloja '$nroloja' não é um inteiro válido." | tee -a $LOG_FILE
            continue
        fi

        # Validar o valor de modelo
        modelo=${chave_nfe:20:2}
        if ! [[ "$modelo" =~ ^-?[0-9]+$ ]]; then
            modelo=0
        fi

        last_nroloja=$nroloja
        lote_sql="${lote_sql}('$PARAM_REDE', '$nroloja', '$DataProc', '$Pdv', '$chave_nfe', '$modelo', 1, '$NroCupom', '$vICMS', '$vICMS_ST', '$vPIS', '$vPIS_ST', '$vCOFINS', '$vCOFINS_ST', '$vFCP', '$vFCP_ST', '$LV', '$estornado', '$DataProc', '$Status'), "
        ((contador++))
        if [ "$contador" -eq 500 ]; then
            lote_sql=${lote_sql%, }
            lote_sql="$lote_sql ON DUPLICATE KEY UPDATE nroloja=VALUES(nroloja), DataProc=VALUES(DataProc), Pdv=VALUES(Pdv), modelo=VALUES(modelo), emServidor=1, nCupom=VALUES(nCupom), vICMS=VALUES(vICMS), vICMS_ST=VALUES(vICMS_ST), vPIS=VALUES(vPIS), vPIS_ST=VALUES(vPIS_ST), vCOFINS=VALUES(vCOFINS), vCOFINS_ST=VALUES(vCOFINS_ST), vFCP=VALUES(vFCP), vFCP_ST=VALUES(vFCP_ST), LV=VALUES(LV), estornado=VALUES(estornado), dEmi=VALUES(DataProc), Status=VALUES(Status);"
            echo "Enviando lote de 500 registros para o BI..." | tee -a $LOG_FILE
            
            INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
            if [ $? -ne 0 ]; then
                echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
            else
                echo "Lote 500 enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
            fi
            contador=0
            lote_sql="INSERT INTO cfe_retorno (rede, nroloja, DataProc, Pdv, Chave, modelo, emServidor, nCupom, vICMS, vICMS_ST, vPIS, vPIS_ST, vCOFINS, vCOFINS_ST, vFCP, vFCP_ST, LV, estornado, dEmi, Status) VALUES "
        fi
    done <<< "$RESULTS"

    if [ "$contador" -gt 0 ]; then
        lote_sql=${lote_sql%, }
        lote_sql="$lote_sql ON DUPLICATE KEY UPDATE nroloja=VALUES(nroloja), DataProc=VALUES(DataProc), Pdv=VALUES(Pdv), modelo=VALUES(modelo), emServidor=1, nCupom=VALUES(nCupom), vICMS=VALUES(vICMS), vICMS_ST=VALUES(vICMS_ST), vPIS=VALUES(vPIS), vPIS_ST=VALUES(vPIS_ST), vCOFINS=VALUES(vCOFINS), vCOFINS_ST=VALUES(vCOFINS_ST), vFCP=VALUES(vFCP), vFCP_ST=VALUES(vFCP_ST), LV=VALUES(LV), estornado=VALUES(estornado), dEmi=VALUES(DataProc), Status=VALUES(Status);"
        echo "Enviando lote final de $contador registros para o BI..." | tee -a $LOG_FILE
        
        INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
        else
            echo "Lote final de $contador enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
        fi
    fi
done

# Lembre-se de remover o arquivo de lock no final do script
rm -f "$LOCK_FILE"
