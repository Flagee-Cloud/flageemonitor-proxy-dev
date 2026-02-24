#!/bin/bash

# Carregar configurações do bot
source /ariusmonitor/config_bot.conf

# Caminho para o arquivo termcons.ini
INI_FILE="/tmp/termcons.ini"

# URL da API do Zabbix
ZABBIX_API="https://$PARAM_ZABBIX_SERVER/api_jsonrpc.php"

PARAM_TOKEN="44ad24e93c4f88e5006fd50e1f879d208c67dd6c67b4064f9c91fbe133a294fa"

# Arquivo de log
LOG_FILE="/ariusmonitor/microterminal.log"

# Função para log com timestamp e cores no terminal
log_with_timestamp() {
    local message="$1"
    local type="$2"  # Tipo: INFO, WARN, ERROR
    local color
    case "$type" in
        INFO) color="\033[0;32m" ;;  # Verde
        WARN) color="\033[0;33m" ;;  # Amarelo
        ERROR) color="\033[0;31m" ;;  # Vermelho
        *) color="\033[0m" ;;  # Sem cor
    esac

    # Formatar mensagem
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local formatted_message="$timestamp - [$type] $message"

    # Exibir no terminal com cor
    echo -e "${color}${formatted_message}\033[0m"

    # Salvar no log
    echo "$formatted_message" >> "$LOG_FILE"
}

# Função para listar hosts concentradores
get_concentrators() {
    local group_id="$1"
    local json='{
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "search": {
                "name": [
                    "CONCENTRADOR"
                ]
            },
            "output": ["hostid", "host", "name", "inventory"],
            "selectInterfaces": ["ip"],
            "selectInventory": ["notes"],
            "selectMacros": ["macro", "value"],
            "filter": {
                "status": [0]
            },
            "groupids": ['"$group_id"']
        },
        "id": 1
    }'
    echo "$json" | curl -sk -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $PARAM_TOKEN" -d @- $ZABBIX_API
}


# Supondo que você já tenha coletado o group_id, use-o aqui
CONCENTRATORS=$(get_concentrators "$PARAM_ZABBIX_GROUPID")
echo "$CONCENTRATORS" > /tmp/concentrators.json

# Função para coletar termcons.ini de um host remoto
collect_termcons() {
    local ip="$1"
    local user="$2"
    local password="$3"
    
    # Limpando arquivo anterior
    >$INI_FILE

    # Usando sshpass para autenticação sem interação
    sshpass -p "$password" scp "${user}@${ip}:/servidor/configuracao/termcons.ini" "$INI_FILE"
    if [[ $? -eq 0 ]]; then
        log_with_timestamp "Arquivo termcons.ini coletado de $ip" "INFO"
    else
        log_with_timestamp "Falha ao coletar termcons.ini de $ip" "ERROR"
    fi
}


# Função para gerenciar o status e o nome do host no Zabbix
manage_host() {
    local host_ip="$1"
    local host="$2"
    local host_name="$3"
    local host_id="$4"
    local desired_status="$5"

    if [[ -z "$host_id" ]]; then
        log_with_timestamp "Host $host_name não encontrado. Criando host..." "INFO"
        
        # JSON para criar o host
        local create_json='{
            "jsonrpc": "2.0",
            "method": "host.create",
            "params": {
                "host": "'"$host"'",
                "name": "'"$host_name"'",
                "interfaces": [
                    {
                        "type": 1,
                        "main": 1,
                        "useip": 1,
                        "ip": "'"$host_ip"'",
                        "dns": "",
                        "port": "10050"
                    }
                ],
                "proxy_hostid": "'"$PARAM_ZABBIX_PROXYID"'",
                "groups": [
                    {
                        "groupid": "'"$PARAM_ZABBIX_GROUPID"'"
                    }
                ],
                "tags": [
                    {
                        "tag": "TIPO_DISPOSITIVO",
                        "value": "TERMINAL_CONSULTA"
                    }
                ],
                "templates": [
                    {"templateid": "10186"}
                ],
                "inventory_mode": 1
            },
            "id": 1
        }'
        
        # Enviar requisição para criar o host
        response=$(echo "$create_json" | curl -sk -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $PARAM_TOKEN" -d @- $ZABBIX_API)
        
        if [[ "$response" == *"error"* ]]; then
            log_with_timestamp "Erro ao criar host $host_name. Resposta: $response" "ERROR"
        else
            log_with_timestamp "Host $host_name criado com sucesso. Resposta: $response" "INFO"
        fi
    else
        # Atualizar o status e o nome no Zabbix se o host já existir
        local update_json='{
            "jsonrpc": "2.0",
            "method": "host.update",
            "params": {
                "hostid": "'"$host_id"'",
                "host": "'"$host"'",
                "name": "'"$host_name"'",
                "status": '"$desired_status"'
            },
            "id": 1
        }'
        
        response=$(echo "$update_json" | curl -sk -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $PARAM_TOKEN" -d @- $ZABBIX_API)
        if [[ "$response" == *"error"* ]]; then
            log_with_timestamp "Erro ao atualizar host ID=$host_id. Resposta: $response" "ERROR"
        else
            log_with_timestamp "Host atualizado: ID=$host_id, Status=$desired_status, Nome=$host_name" "INFO"
        fi
    fi
}


# Consultar múltiplos hosts no Zabbix
get_hosts_in_batch() {
    local ip_list="$1"
    local json='{
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "status", "host", "name", "interfaces"],
            "selectInterfaces": ["ip"],
            "filter": {
                "ip": ['"$ip_list"']
            },
            "groupids": ['"$PARAM_ZABBIX_GROUPID"']
        },
        "id": 1
    }'
    echo "$json" | curl -sk -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $PARAM_TOKEN" -d @- $ZABBIX_API
}


# Processar a lista de concentradores
jq -c '.result[]' /tmp/concentrators.json | while read -r concentrator; do
    host_id=$(echo "$concentrator" | jq -r '.hostid')
    host_name=$(echo "$concentrator" | jq -r '.name')
    ip=$(echo "$concentrator" | jq -r '.interfaces[0].ip')
    notes=$(echo "$concentrator" | jq -r '.inventory.notes')
    
    # Obter macro {$CONCENTRADOR_LOJA}
    macro_loja=$(echo "$concentrator" | jq -r '.macros[] | select(.macro == "{$CONCENTRADOR_LOJA}").value // empty')

    # Separar credenciais das notas
    IFS=',' read -r user password <<< "$notes"

    # Coletar termcons.ini
    collect_termcons "$ip" "$user" "$password"
    
    # Após coletar o arquivo, processar conforme o fluxo existente
    echo "Iniciando leitura do arquivo termcons.ini em $host_name"
    
    declare -A TERMINALS
    while IFS= read -r line; do
        if [[ "$line" =~ ^\#\[(Terminal-[0-9]+).* ]]; then  # Verifica terminal comentado
            terminal=${BASH_REMATCH[1]}
            NumeroTerminal=$(echo "$terminal" | sed 's/Terminal-//')
            Ativo=1  # Comentado = Inativo
            Comentado=true
            # log_with_timestamp "Terminal $terminal comentado encontrado. Marcado como inativo (Ativo=1)." "DEBUG"
        elif [[ "$line" =~ ^\[(Terminal-[0-9]+).* ]]; then  # Terminal não comentado
            terminal=${BASH_REMATCH[1]}
            NumeroTerminal=$(echo "$terminal" | sed 's/Terminal-//')
            Ativo=0  # Não comentado = Ativo
            Comentado=false
            # log_with_timestamp "Terminal $terminal não comentado encontrado. Marcado como ativo (Ativo=0)." "DEBUG"
        fi

        # Tratar IP e Loja mesmo que as linhas estejam comentadas
        if [[ "$line" =~ ^[#]*IP[[:space:]]*=[[:space:]]*(.+)$ ]]; then
            IP=$(echo "${BASH_REMATCH[1]}" | xargs)
            # log_with_timestamp "IP encontrado: $IP (Comentado=$Comentado)" "DEBUG"
        fi
        if [[ "$line" =~ ^[#]*Loja[[:space:]]*=[[:space:]]*(.+)$ ]]; then
            Loja=$(echo "${BASH_REMATCH[1]}" | xargs | sed 's/^0*//')
            Loja=$(printf "%03d" "$Loja")
            # log_with_timestamp "Loja encontrada: $Loja (Comentado=$Comentado)" "DEBUG"
        fi

        # Processar o terminal ao encontrar uma linha vazia
        if [[ -z "$line" ]]; then
            # Fallback para macro {$CONCENTRADOR_LOJA} se Loja não for encontrada
            if [[ -z "$Loja" && -n "$macro_loja" ]]; then
                Loja=$(printf "%03d" "$macro_loja")
                # log_with_timestamp "Usando macro {$CONCENTRADOR_LOJA} para Loja: $Loja" "DEBUG"
            fi

            # Verificar se todas as variáveis estão preenchidas antes do armazenamento
            if [[ -n "$IP" && -n "$Loja" && -n "$NumeroTerminal" ]]; then
                Host="$PARAM_REDE-LOJA$Loja-TC$NumeroTerminal"
                HostName="$PARAM_REDE (LOJA$Loja) TC$NumeroTerminal"

                # Armazenar no array
                # log_with_timestamp "Armazenando terminal: IP=$IP, Host=$Host, HostName=$HostName, Loja=$Loja, NumeroTerminal=$NumeroTerminal, Ativo=$Ativo" "DEBUG"
                TERMINALS["$IP"]="$Host|$HostName|$Loja|$NumeroTerminal|$Ativo"
            # else
                # Mostrar exatamente o que está faltando
                # log_with_timestamp "Dados incompletos para terminal $terminal. Não armazenado. Variáveis: IP=${IP:-<vazio>}, Loja=${Loja:-<vazio>}, NumeroTerminal=${NumeroTerminal:-<vazio>}" "WARN"
            fi

            # Reset das variáveis APÓS o processamento
            IP=""
            Loja=""
            Host=""
            HostName=""
            Comentado=""
            Ativo=""
        fi
    done < "$INI_FILE"



    # Verificar se TERMINALS está vazio
    if [[ ${#TERMINALS[@]} -eq 0 ]]; then
        log_with_timestamp "Nenhum terminal encontrado em $host_name. Continuando..." "WARN"
        continue
    fi

    # Processar cada terminal no array TERMINALS
    for ip in "${!TERMINALS[@]}"; do
        IFS="|" read -r Host HostName Loja NumeroTerminal Ativo <<< "${TERMINALS[$ip]}"
        
        log_with_timestamp "Processando terminal: IP=$ip, Host=$Host, HostName=$HostName, Ativo=$Ativo" "DEBUG"

        # Verificar se o host já existe no Zabbix usando o IP
        response=$(get_hosts_in_batch "\"$ip\"")
        if [[ -z "$response" ]]; then
            log_with_timestamp "Nenhuma resposta do Zabbix para o IP $ip. Pulando este terminal." "ERROR"
            continue
        fi

        host_id=$(echo "$response" | jq -r '.result[0].hostid // empty')
        host=$(echo "$response" | jq -r '.result[0].host // empty')
        host_name=$(echo "$response" | jq -r '.result[0].name // empty')
        host_status=$(echo "$response" | jq -r '.result[0].status // empty')

        if [[ -z "$host_id" ]]; then
            if [[ "$Ativo" -eq 1 ]]; then
                log_with_timestamp "Host para IP $ip não encontrado, e o status é inativo (Ativo=1). Não será criado no Zabbix." "INFO"
            else
                log_with_timestamp "Host para IP $ip não encontrado. Criando host $HostName." "INFO"
                manage_host "$ip" "$Host" "$HostName" "" "$Ativo"
            fi
        else
            log_with_timestamp "Host encontrado: ID=$host_id, Host=$host, Host Name=$host_name, IP=$ip" "DEBUG"

            # Verifique e atualize o status e outros detalhes se necessário
            if [[ "$host_status" != "$Ativo" ]]; then
                log_with_timestamp "Atualizando status do host $HostName (ID=$host_id) de $host_status para $Ativo." "INFO"
                manage_host "$ip" "$Host" "$HostName" "$host_id" "$Ativo"
            elif [[ "$host" != "$Host" || "$host_name" != "$HostName" ]]; then
                log_with_timestamp "Atualizando detalhes do host $HostName devido a diferenças detectadas." "INFO"
                manage_host "$ip" "$Host" "$HostName" "$host_id" "$Ativo"
            else
                log_with_timestamp "Host $HostName já está no status correto ($Ativo)." "INFO"
            fi
        fi
    done

done
