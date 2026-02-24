#!/bin/bash

source /ariusmonitor/config_bot.conf

BASE_DIR="/ariusmonitor"
DB_NAME="controle"

SQL_QUERY="SELECT nroloja, ChaveConciliaSat FROM conf_nfce WHERE LENGTH(ChaveConciliaSat) = 36"
echo $SQL_QUERY

for DB_HOST in "${PARAM_IP_CONCENTRADORES[@]}"
do
    echo "Conectando ao IP $DB_HOST"

    QUERY_RESULT=$(timeout 10 mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$SQL_QUERY" -B -N)
    
    if [ $? -eq 124 ]; then
        echo "Timeout"
        continue
    fi
    
    if [ -z "$QUERY_RESULT" ]; then
        echo "Nenhum dado retornado ou erro na execução da consulta"
        continue
    fi
    
    echo "$QUERY_RESULT" | while IFS=$'\t' read -r nroloja ChaveConciliaSat
    do
        mysql -h"$DB_HOST_BI" -u"$DB_USER_BI" -p"$DB_PASS_BI" -D"$DB_NAME_BI" -e "INSERT IGNORE INTO conf_nfce (rede, nroloja, chaveSeguranca) VALUES ('$PARAM_REDE', '$nroloja', '$ChaveConciliaSat')"
        if [ $? -ne 0 ]; then
            echo "Erro ao inserir dados no banco BI para LOJA: $nroloja - CHAVE: $ChaveConciliaSat"
        else
            echo "Inserido/Ignorado Loja para LOJA: $nroloja - CHAVE: $ChaveConciliaSat"
        fi
    done

done
