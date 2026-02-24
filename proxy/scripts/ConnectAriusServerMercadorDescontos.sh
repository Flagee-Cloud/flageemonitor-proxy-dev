#!/bin/bash

# Sourcing the configuration file
source /ariusmonitor/config_bot.conf

LOG_DIR="$PARAM_BASE_DIR/logs"
LOCK_FILE="$PARAM_BASE_DIR/script_mercador_descontos.lock"
DB_NAME="retag"

# Garantir que o diretório de logs existe
mkdir -p "$LOG_DIR"

# Arquivo de log
LOG_FILE="$LOG_DIR/script_log_mercador_descontos.txt"
>$LOG_FILE

# Inicializando contador geral
contadorGeral=0

# Diretório temporário para arquivos CSV
TMP_DIR="/tmp/mercador_csv"
mkdir -p "$TMP_DIR"

# Loop para processar hosts
for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"; do
    echo "Conectando ao IP $DB_HOST" | tee -a $LOG_FILE
    offset=0
    batch_size=10000

    while true; do
        # Criar tabela temporária no BIVarejo antes de cada lote
        echo "Criando tabela temporária no BIVarejo..." | tee -a $LOG_FILE
        mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" --execute="
        CREATE TEMPORARY TABLE IF NOT EXISTS mercador_descontos_tmp (
            empresa_id INT(4) NOT NULL,
            loja_codigo INT NOT NULL DEFAULT 0,
            codigoean BIGINT UNSIGNED NOT NULL,
            percentualPLU2 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
            percentualPLU3 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
            percentualPLU4 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
            percentualPLU5 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
            percentualPLU6 DECIMAL(5,2) NOT NULL DEFAULT 0.00,
            precoPLU2 DECIMAL(9,3) NOT NULL DEFAULT 0.000,
            precoPLU3 DECIMAL(9,3) NOT NULL DEFAULT 0.000,
            precoPLU4 DECIMAL(9,3) NOT NULL DEFAULT 0.000,
            precoPLU5 DECIMAL(9,3) NOT NULL DEFAULT 0.000,
            precoPLU6 DECIMAL(9,3) NOT NULL DEFAULT 0.000,
            max_merc_plu2 INT NOT NULL DEFAULT 0,
            max_merc_plu3 INT NOT NULL DEFAULT 0,
            max_merc_plu4 INT NOT NULL DEFAULT 0,
            max_merc_plu5 INT NOT NULL DEFAULT 0,
            max_merc_plu6 INT NOT NULL DEFAULT 0
        );
        " 2>>"$LOG_FILE"

        # Arquivo CSV temporário
        CSV_FILE="$TMP_DIR/mercador_${DB_HOST}_${offset}.csv"
        > "$CSV_FILE"

        # Consulta SQL com paginação
        SQL_QUERY="SELECT '$PARAM_EMPRESA_ID', nroloja, codigoean, percentualPLU2, percentualPLU3, percentualPLU4, percentualPLU5, percentualPLU6, precoPLU2, precoPLU3, precoPLU4, precoPLU5, precoPLU6, max_merc_plu2, max_merc_plu3, max_merc_plu4, max_merc_plu5, max_merc_plu6 FROM PluDif LIMIT $batch_size OFFSET $offset;"

        # Exportar para CSV
        mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" --batch --silent --execute="$SQL_QUERY" --skip-column-names > "$CSV_FILE"

        # Verifica se o arquivo CSV está vazio (fim dos dados)
        if [ ! -s "$CSV_FILE" ]; then
            rm -f "$CSV_FILE"
            break
        fi

        # Carregar dados no banco de destino usando LOAD DATA INFILE
        echo "Carregando dados do arquivo $CSV_FILE para a tabela temporária..." | tee -a $LOG_FILE
        LOAD_ERROR=$(mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" --local-infile=1 -e \
        "LOAD DATA LOCAL INFILE '$CSV_FILE' INTO TABLE mercador_descontos_tmp \
        FIELDS TERMINATED BY '\t' \
        LINES TERMINATED BY '\n' \
        (empresa_id, loja_codigo, codigoean, percentualPLU2, percentualPLU3, percentualPLU4, percentualPLU5, percentualPLU6, precoPLU2, precoPLU3, precoPLU4, precoPLU5, precoPLU6, max_merc_plu2, max_merc_plu3, max_merc_plu4, max_merc_plu5, max_merc_plu6);" 2>&1)

        if [ $? -ne 0 ]; then
            echo "Erro ao carregar dados na tabela temporária: $LOAD_ERROR" | tee -a $LOG_FILE
            break
        else
            echo "Dados carregados com sucesso do arquivo $CSV_FILE para a tabela temporária" | tee -a $LOG_FILE
        fi

        # Inserir dados na tabela final com UPDATE
        echo "Inserindo e atualizando dados na tabela final mercador_descontos..." | tee -a $LOG_FILE
        INSERT_ERROR=$(mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" --execute="
        INSERT INTO mercador_descontos
        SELECT * FROM mercador_descontos_tmp
        ON DUPLICATE KEY UPDATE
        percentualPLU2=VALUES(percentualPLU2), percentualPLU3=VALUES(percentualPLU3), percentualPLU4=VALUES(percentualPLU4), percentualPLU5=VALUES(percentualPLU5), percentualPLU6=VALUES(percentualPLU6),
        precoPLU2=VALUES(precoPLU2), precoPLU3=VALUES(precoPLU3), precoPLU4=VALUES(precoPLU4), precoPLU5=VALUES(precoPLU5), precoPLU6=VALUES(precoPLU6),
        max_merc_plu2=VALUES(max_merc_plu2), max_merc_plu3=VALUES(max_merc_plu3), max_merc_plu4=VALUES(max_merc_plu4), max_merc_plu5=VALUES(max_merc_plu5), max_merc_plu6=VALUES(max_merc_plu6);
        " 2>&1)

        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados na tabela final: $INSERT_ERROR" | tee -a $LOG_FILE
        else
            echo "Dados inseridos e atualizados com sucesso na tabela final" | tee -a $LOG_FILE
        fi

        # Remover arquivo temporário
        rm -f "$CSV_FILE"

        # Incrementar offset
        offset=$((offset + batch_size))
    done

done

echo "Total de registros processados: $contadorGeral" | tee -a $LOG_FILE

# Lembre-se de remover o arquivo de lock no final do script
rm -f "$LOCK_FILE"

# Remover diretório temporário
rm -rf "$TMP_DIR"
