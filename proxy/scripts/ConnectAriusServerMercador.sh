#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_mercador.lock"
DB_NAME="retag"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log_mercador.txt"
>$LOG_FILE

# Função para escapar strings para SQL
escape_sql() {
    local value="$1"
    echo "$value" | sed "s/'/''/g"
}

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
    trap "rm -f $LOCK_FILE" EXIT
fi

# Definir a consulta SQL com base nos parâmetros fornecidos
if [ -z "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, codigoint, codigoean, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo FROM mercador WHERE DATE(dthr_alt) = CURDATE();"
elif [ -n "$dtini" ] && [ -z "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, codigoint, codigoean, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo FROM mercador WHERE dthr_alt >= '$dtini';"
elif [ -n "$dtini" ] && [ -n "$dtfim" ]; then
    SQL_QUERY="SELECT nroloja, codigoint, codigoean, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo FROM mercador WHERE dthr_alt BETWEEN '$dtini' AND '$dtfim';"
fi

contadorGeral=0

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"; do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE
    contador=0

    lote_sql="INSERT INTO mercador (empresa_id, loja_codigo, codigoint, codigoean, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo) VALUES "
    last_nroloja=""

    # Use < <(...) para evitar subshell
    while IFS=$'\t' read -r nroloja codigoint codigoean depto valor descricao_completa descricao dataalt dthr_alt validade desconto unidade Grupo; do
        # Escape os valores para SQL
        descricao_completa=$(escape_sql "$descricao_completa")
        descricao=$(escape_sql "$descricao")

        # Adicionar ao lote
        lote_sql="${lote_sql}('$PARAM_EMPRESA_ID', '$nroloja', '$codigoint', '$codigoean', '$depto', '$valor', '$descricao_completa', '$descricao', '$dataalt', '$dthr_alt', '$validade', '$desconto', '$unidade', '$Grupo'), "
        ((contador++))
        ((contadorGeral++))

        # Enviar lote a cada 500 registros
        if [ "$contador" -eq 500 ]; then
            lote_sql=${lote_sql%, }
            lote_sql="$lote_sql ON DUPLICATE KEY UPDATE depto=VALUES(depto), valor=VALUES(valor), descricao_completa=VALUES(descricao_completa), descricao=VALUES(descricao), dataalt=VALUES(dataalt), dthr_alt=VALUES(dthr_alt), desconto=VALUES(desconto), unidade=VALUES(unidade), Grupo=VALUES(Grupo)"

            echo "Enviando lote de 500 registros para o BI..." | tee -a $LOG_FILE

            INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
            if [ $? -ne 0 ]; then
                echo "Erro ao inserir dados no banco BI: $INSERT_ERROR" | tee -a $LOG_FILE
            else
                echo "Lote 500 enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
            fi
            contador=0
            lote_sql="INSERT INTO mercador (empresa_id, loja_codigo, codigoint, codigoean, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo) VALUES "
        fi
    done < <(timeout 300 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names 2>>"$LOG_FILE")

    # Enviar o lote final
    if [ "$contador" -gt 0 ]; then
        lote_sql=${lote_sql%, }
        lote_sql="$lote_sql ON DUPLICATE KEY UPDATE depto=VALUES(depto), valor=VALUES(valor), descricao_completa=VALUES(descricao_completa), descricao=VALUES(descricao), dataalt=VALUES(dataalt), dthr_alt=VALUES(dthr_alt), desconto=VALUES(desconto), unidade=VALUES(unidade), Grupo=VALUES(Grupo);"

        echo "Enviando lote final de $contador registros para o BIVarejo..." | tee -a $LOG_FILE

        INSERT_ERROR=$( /usr/bin/mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "$lote_sql" 2>&1 )
        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados no banco BIVarejo: $INSERT_ERROR" | tee -a $LOG_FILE
            send_zabbix_trap "erro" "Erro ao inserir lote final no banco BIVarejo: $INSERT_ERROR"
        else
            echo "Lote final de $contador enviado com sucesso para LOJA: $last_nroloja" | tee -a $LOG_FILE
            send_zabbix_trap "sucesso" "Lote final de $contador registros enviado com sucesso para LOJA: $last_nroloja"
        fi
    fi
done

echo "Total de registros processados: $contadorGeral" | tee -a $LOG_FILE

# Lembre-se de remover o arquivo de lock no final do script
rm -f "$LOCK_FILE"
