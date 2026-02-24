#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_mercador_grupos.lock"
DB_NAME="retag"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log_mercador_grupos.txt"
>$LOG_FILE

# Inicializando contador geral
contadorGeral=0

# Diretório temporário para arquivos CSV
TMP_DIR="/tmp/mercador_grupos_csv"
mkdir -p "$TMP_DIR"

SET SESSION sql_mode = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

# Loop para processar hosts
for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"; do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE
    offset=0
    batch_size=10000

    while true; do
        # Arquivo CSV temporário
        CSV_FILE="$TMP_DIR/mercador_${DB_HOST}_${offset}.csv"
        > "$CSV_FILE"

        # Consulta SQL com paginação
        SQL_QUERY="SELECT '$PARAM_EMPRESA_ID' AS empresa_id, 
                   nroloja AS loja_codigo, 
                   codigoean, 
                   codigoint, 
                   IF(depto = '' OR depto IS NULL, 0, depto) AS depto, 
                   valor, 
                   CONCAT('\"', REPLACE(descricao_completa, '\"', '\"\"'), '\"') AS descricao_completa, 
                   CONCAT('\"', REPLACE(descricao, '\"', '\"\"'), '\"') AS descricao, 
                   LEFT(dataalt, 6) AS dataalt, 
                   dthr_alt, 
                   LEFT(validade, 3) AS validade, 
                   desconto, 
                   estoque, 
                   estoque_atual, 
                   Grupo 
            FROM mercador 
            LIMIT $batch_size OFFSET $offset;"


        # Exportar para CSV
        mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names > "$CSV_FILE"

        if [ ! -s "$CSV_FILE" ]; then
            echo "Erro: Arquivo CSV vazio ou não gerado: $CSV_FILE" | tee -a $LOG_FILE
            break
        fi

        # Desativar SQL_MODE antes de carregar dados
        mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" --execute="SET SESSION sql_mode = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';"

        # Carregar dados no banco de destino usando LOAD DATA INFILE
        echo "Carregando dados do arquivo $CSV_FILE para a tabela intermediária no BIVarejo..." | tee -a $LOG_FILE
        LOAD_ERROR=$(mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" --local-infile=1 -e \
        "LOAD DATA LOCAL INFILE '$CSV_FILE' INTO TABLE mercador_intermediaria
FIELDS TERMINATED BY '\t' 
OPTIONALLY ENCLOSED BY '\"' 
LINES TERMINATED BY '\n'
(empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dthr_alt, validade, desconto, estoque, estoque_atual, Grupo);" 2>&1)

        if [ $? -ne 0 ];then
            echo "Erro ao carregar dados na tabela intermediária no BIVarejo: $LOAD_ERROR" | tee -a $LOG_FILE
            break
        else
            echo "Dados carregados com sucesso do arquivo $CSV_FILE para a tabela intermediária no BIVarejo" | tee -a $LOG_FILE
        fi

        # Inserir dados na tabela final com UPDATE
        echo "Inserindo e atualizando dados na tabela final mercador no BIVarejo..." | tee -a $LOG_FILE
        INSERT_ERROR=$(mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" --execute="
        INSERT INTO mercador (empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dthr_alt, validade, desconto, estoque, estoque_atual, Grupo)
        SELECT empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dthr_alt, validade, desconto, estoque, estoque_atual, Grupo
        FROM mercador_intermediaria
        ON DUPLICATE KEY UPDATE
        depto=VALUES(depto), valor=VALUES(valor), descricao_completa=VALUES(descricao_completa), descricao=VALUES(descricao), dthr_alt=VALUES(dthr_alt), desconto=VALUES(desconto), estoque=VALUES(estoque), estoque_atual=VALUES(estoque_atual), Grupo=VALUES(Grupo);
        TRUNCATE TABLE mercador_intermediaria;
        " 2>&1)

        if [ $? -ne 0 ];then
            echo "Erro ao inserir dados na tabela final mercador no BIVarejo: $INSERT_ERROR" | tee -a $LOG_FILE
        else
            echo "Dados inseridos e atualizados com sucesso na tabela final mercador no BIVarejo" | tee -a $LOG_FILE
        fi

        # Não remover arquivo temporário para depuração
        echo "Arquivo CSV mantido para análise: $CSV_FILE" | tee -a $LOG_FILE

        # Incrementar offset
        offset=$((offset + batch_size))
    done

done

echo "Total de registros processados: $contadorGeral" | tee -a $LOG_FILE

# Lembre-se de remover o arquivo de lock no final do script
rm -f "$LOCK_FILE"

# Remover diretório temporário
rm -rf "$TMP_DIR"