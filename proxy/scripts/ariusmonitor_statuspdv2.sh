#!/bin/bash

# Define o ambiente
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
export LANG=C.UTF-8

# Caminho para o arquivo de bloqueio
lockfile="/tmp/update_status.lock"

# Caminho para o arquivo de log
logfile="/var/log/update_status.log"


# Verifica se o arquivo de bloqueio existe
if [ -f "$lockfile" ]; then
    echo "O script já está em execução."
    exit 1
fi

# Cria o arquivo de bloqueio
touch "$lockfile"

echo "$(date +'%Y-%m-%d %H:%M:%S') - Executando Query." >> "$logfile"

# Conectar ao MariaDB e executar o script SQL
/usr/bin/mariadb -u zabbix -p741258ABCcba -D zabbix <<EOF 2>>"$logfile" 1>>"$logfile"
INSERT INTO FlageeStatusCaixa (data_hora, caixa, status)
    WITH RelevantHosts AS (
        SELECT
            hostid,
            name as caixa
        FROM
            hosts
        WHERE
            (name LIKE '%PDV%' or name LIKE '%SELF%')
            AND status = 0
    ),
    Desligado AS (
        SELECT
            rh.caixa,
            triggers.value as desligado
        FROM
            triggers
        JOIN functions ON functions.triggerid = triggers.triggerid
        JOIN items ON items.itemid = functions.itemid
        JOIN RelevantHosts rh ON items.hostid = rh.hostid
        WHERE
            triggers.status = 0 AND
            triggers.value = 1 AND
            /*triggers.state = 0 AND*/
            triggers.description = 'INFORMATIVO: Equipamento Desligado Corretamente'
        GROUP BY
            rh.hostid
    ),
    DesligadoIncorretamente AS (
        SELECT
            rh.caixa,
            triggers.value as desligado_incorretamente
        FROM
            triggers
        JOIN functions ON functions.triggerid = triggers.triggerid
        JOIN items ON items.itemid = functions.itemid
        JOIN RelevantHosts rh ON items.hostid = rh.hostid
        WHERE
            triggers.status = 0 AND
            /*triggers.value = 1 AND*/
            triggers.state = 0 AND
            triggers.description = 'Host sem comunicação ou desligado de forma incorreta / travado por mais de 10 minutos'
        GROUP BY
            rh.hostid
    ),
    DisasterIncidents AS (
        SELECT
            rh.caixa,
            COUNT(DISTINCT triggers.triggerid) AS IncidentCount
        FROM
            triggers
        JOIN functions ON functions.triggerid = triggers.triggerid
        JOIN items ON items.itemid = functions.itemid
        JOIN RelevantHosts rh ON items.hostid = rh.hostid
        WHERE
            triggers.status = 0 AND
            /*triggers.state = 0 AND*/
            triggers.value = 1 AND
            triggers.priority = 5 AND
            triggers.description != 'Host sem comunicação ou desligado de forma incorreta / travado por mais de 10 minutos'
        GROUP BY
            rh.hostid
    ),
    CaixaAberto AS (
        SELECT
            rh.caixa,
            MAX(ht.value) AS caixa_aberto_valor
        FROM
            history_text ht
        JOIN items ON ht.itemid = items.itemid
        JOIN RelevantHosts rh ON items.hostid = rh.hostid
        WHERE
            items.name = 'PDV (ID Operador Caixa)' AND
            ht.clock BETWEEN UNIX_TIMESTAMP() - 300 AND UNIX_TIMESTAMP()
        GROUP BY
            rh.hostid
    ),
    CaixaSemVendas AS (
        SELECT
            rh.caixa,
            MAX(ht.value) AS caixa_aberto_valor
        FROM
            history_text ht
        JOIN items ON ht.itemid = items.itemid
        JOIN RelevantHosts rh ON items.hostid = rh.hostid
        WHERE
            items.name = 'PDV (ID Operador Caixa)' AND
            ht.clock BETWEEN UNIX_TIMESTAMP() - 300 AND UNIX_TIMESTAMP()
        GROUP BY
            rh.hostid
    )
    SELECT
        current_timestamp,
        rh.caixa,
        CASE 
            WHEN COALESCE(di.IncidentCount, 0) > 0 THEN 4
            WHEN COALESCE(din.desligado_incorretamente, 0) = 1 THEN 3
            WHEN COALESCE(de.desligado, 0) = 1 THEN 2
            WHEN COALESCE(ca.caixa_aberto_valor, '') = '' AND COALESCE(de.desligado, 0) = 0 THEN 1
            ELSE 0
        END AS status
    FROM
        RelevantHosts rh
    LEFT JOIN
        DisasterIncidents di ON rh.caixa = di.caixa
    LEFT JOIN
        CaixaAberto ca ON rh.caixa = ca.caixa
    LEFT JOIN
        Desligado de ON rh.caixa = de.caixa
    LEFT JOIN
        DesligadoIncorretamente din ON rh.caixa = din.caixa
    GROUP BY
        rh.caixa
EOF

if [ $? -eq 0 ]; then
    echo "$(date +'%Y-%m-%d %H:%M:%S') - Query executada com sucesso." >> "$logfile"
else
    echo "$(date +'%Y-%m-%d %H:%M:%S') - Erro ao executar a query." >> "$logfile"
fi

# Remove o arquivo de bloqueio
rm "$lockfile"