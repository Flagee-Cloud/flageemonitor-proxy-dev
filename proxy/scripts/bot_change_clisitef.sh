#!/bin/bash


# Definindo códigos de cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variaveis globais
ARIUSMONTIOR_BOT_DIR="/ariusmonitor"


# Parametros shellscript
PARAM_PDV_IP=""
PARAM_PDV=""
PARAM_CREDENCIAIS_INVALIDAS="false"
PARAM_DEBBUG="false"
PARAM_CHANGE_CLISITEF="false"

# Carregue as variáveis do arquivo de configuração
source $ARIUSMONTIOR_BOT_DIR/config_bot.conf


# Analisando os parâmetros
TEMP=$(getopt -o h --long help,rede:,loja:,pdv:,pdv-ip:,debbug,change-clisitef -- "$@")
eval set -- "$TEMP"

while true; do
  case $1 in
    --pdv-ip)
      PARAM_PDV_IP="$2"
      shift 2
      ;;
    --rede)
      PARAM_REDE="$2"
      shift 2
      ;;
    --loja)
      PARAM_LOJA="$2"
      shift 2
      ;;    
    --agent-status)
      PARAM_AGENT_STATUS="$2"
      shift 2
      ;;
    --credenciais-invalidas)
      PARAM_CREDENCIAIS_INVALIDAS="true"
      shift
      ;;
    --pdv)
      PARAM_PDV="$2"
      shift 2
      ;;
    --debbug)
      PARAM_DEBBUG="true"
      shift
      ;;
    --change-clisitef)
      PARAM_CHANGE_CLISITEF="true"
      shift
      ;;
    --)
      shift
      break
      ;;
  esac
done

echo -e "${BLUE}LOJA: ${PARAM_REDE} - PROXY: ${PARAM_PROXY_IP}${NC}"

# Definir arquivos de log
LOGFILE_GENERAL="/ariusmonitor/logfile_general.log"
LOGFILE_INVALID_CREDENTIALS="/ariusmonitor/logfile_invalid_credentials.log"
LOGFILE_MONITORASAT="/ariusmonitor/logfile_monitorasat.log"
LOGFILE_HTCONFIG_NOTINSTALLED="/ariusmonitor/logfile_htcconfig_notinstalled.log"
LOGFILE_MACHINE_UNRESPONSIVE="/ariusmonitor/logfile_machine_unresponsive.log"


# Função para registrar LOG
log() {
  MESSAGE="$1"
  COLOR="${2:-$NC}"
  LOGFILE="$3"

  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

  # Escrever mensagem com cor no terminal
  echo -e "${COLOR}${TIMESTAMP} - ${MESSAGE}${NC}"

  # Escrever mensagem no arquivo de log geral
  echo -e "${TIMESTAMP} - ${MESSAGE}" >> "$LOGFILE_GENERAL"

  # Se um arquivo de log específico foi fornecido, escrever a mensagem nele também
  if [ -n "$LOGFILE" ]; then
    echo -e "${TIMESTAMP} - ${MESSAGE}" >> "$LOGFILE"
  fi
}

# Função para capturar o sinal SIGINT (CTRL+C)
interrupt_handler() {
  log "Interrompendo a execução do script..."
  pkill -P $$ # Encerra todos os processos filho do script (incluindo conexões SSH)
  exit 1
}

# Definir o manipulador de interrupção para o sinal SIGINT
trap interrupt_handler SIGINT

# Verifique se o arquivo config_bot.conf existe
if [ ! -f "$ARIUSMONTIOR_BOT_DIR/config_bot.conf" ]; then
  log "Arquivo de configuração '$ARIUSMONTIOR_BOT_DIR/config_bot.conf' não encontrado!" "$RED"
  exit 1
fi

# Verifica o fuso horário atual
CURRENT_TIMEZONE=$(timedatectl show --property=Timezone --value)

# Verifica se o fuso horário atual é America/Sao_Paulo
if [ "$CURRENT_TIMEZONE" != "America/Sao_Paulo" ]; then
    log "Corrigindo fuso horário para America/Sao_Paulo..."
    sudo timedatectl set-timezone America/Sao_Paulo
else
    log "Fuso horário: America/Sao_Paulo."
fi


#### CHECAGEM DE PARÂMETROS PARA FILTRO DA API ZABBIX ####

# Inicializar variáveis para filtro
filtro_host=""
filtro_host_ip=""

# Verifica e constrói o filtro com base nos parâmetros fornecidos
if [ -n "$PARAM_LOJA" ] && [ -n "$PARAM_PDV" ]; then
    # Caso --loja e --pdv sejam fornecidos
    filtro_host="${PARAM_LOJA}-${PARAM_PDV}"

elif [ -n "$PARAM_LOJA" ]; then
    # Caso apenas --loja seja fornecido
    filtro_host="${PARAM_LOJA}"

elif [ -n "$PARAM_PDV_IP" ]; then
    # Caso apenas --pdv-ip seja fornecido
    # Aqui você precisará adaptar a busca para corresponder à lógica específica do seu Zabbix
    # Este exemplo assume que você pode buscar hosts diretamente por um campo que represente o IP
    filtro_host_ip=",\"filter\": {\"ip\": \"$PARAM_PDV_IP\"}"
fi

log "###### Iniciando Bot Arius Monitor para $PARAM_REDE $PARAM_LOJA $PARAM_PDV $PARAM_PDV_IP" "$GREEN"


#### FIM DA CHECAGEM DE PARÂMETROS ####




# Função para verificar a conectividade com a máquina de destino
check_connection() {
  local IP="$1"
  local USER="$2"
  local PASS="$3"

  timeout 5 bash -c "echo >/dev/tcp/$IP/22" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    return 1 # Máquina não responde
  fi

  # Remove a entrada antiga da chave do host no arquivo known_hosts
  ssh-keygen -R "$IP" >/dev/null 2>&1

  OUTPUT=$(timeout 30 sshpass -p "$PASS" ssh -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-dss -o CheckHostIP=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$USER@$IP" exit >/dev/null 2>&1)
  CONNECTION_STATUS=$?

  if [ $CONNECTION_STATUS -ne 0 ]; then
    return 2 # Credenciais inválidas
  fi

  return 0 # Conexão bem-sucedida
}

# Função para detectar a distribuição e a versão do Linux na máquina de destino
detect_distro_and_version() {
  local IP="$1"
  local USER="$2"
  local PASS="$3"

  # Verifica se o comando lsb_release está disponível
  LSB_RELEASE_EXISTS=$(timeout 30 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss "$USER@$IP" "which lsb_release 2>&1 | grep -v 'no lsb_release' | wc -l")

  if [ "$LSB_RELEASE_EXISTS" = "1" ]; then
    # Utilize o lsb_release para identificar a distribuição e versão
    DISTRO_INFO=$(timeout 30 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss "$USER@$IP" "lsb_release -a 2>/dev/null")
  else
    # Tratamento alternativo para Slackware
    DISTRO_INFO=$(timeout 30 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss "$USER@$IP" "cat /etc/slackware-version 2>/dev/null")
  fi

  DISTRO=""
  VERSION=""

  if echo "$DISTRO_INFO" | grep -qi "Distributor ID:\s*Ubuntu"; then
    DISTRO="Ubuntu"
    VERSION=$(echo "$DISTRO_INFO" | grep -oP 'Release:\s*\K\d+')
  elif echo "$DISTRO_INFO" | grep -qi "Distributor ID:\s*LinuxMint"; then
    DISTRO="Mint"
    VERSION=$(echo "$DISTRO_INFO" | grep -oP 'Release:\s*\K\d+')
  elif echo "$DISTRO_INFO" | grep -qi "Slackware"; then
    DISTRO="Slackware"
    VERSION=$(echo "$DISTRO_INFO" | grep -oP 'Slackware \K\d+')
  else
    echo "unknown"
    return
  fi

  echo "$DISTRO $VERSION"
}

detect_architecture() {
  local IP="$1"
  local USER="$2"
  local PASS="$3"

  ARCHITECTURE=$(timeout 30 sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss "$USER@$IP" "uname -m" 2>/dev/null)

  if [ -n "$ARCHITECTURE" ]; then
    case "$ARCHITECTURE" in
      i?86) ARCHITECTURE="i386" ;;
      x86_64) ARCHITECTURE="amd64" ;;
      *) ARCHITECTURE="unknown" ;;
    esac
  else
    ARCHITECTURE="unknown"
  fi

  echo "$ARCHITECTURE"
}

# Define uma função auxiliar para executar comandos sshpass
run_sshpass() {
    local cmd=$1
    local USER="$2"
    local PASS="$3"
    local IP="$4"
    local DEBBUG_INDIVIDUAL="$5"

    # Execute o comando e capture a saída e a saída de erro
    local output=$(timeout 30 sshpass -p "$PASS" ssh -T -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss "$USER@$IP" "$cmd" 2>&1)

    # Verifique o status de saída do sshpass
    local exit_status=$?

    # Faça o log da saída e do status de saída
    if [ "$PARAM_DEBBUG" == "true" ]; then
      log "Comando: $cmd"
      log "Saída:$YELLOW $output $NC"
      log "Status de saída: $exit_status"
    fi

    if [ "$DEBBUG_INDIVIDUAL" == "true" ]; then
      log "Comando: $cmd"
      log "**** Retorno:$YELLOW $output $NC" "" "$LOGFILE_MONITORASAT"
    fi

    if [ $exit_status -ne 0 ]; then
        log "Falha ao executar o comando: $cmd"
        exit 1
    fi
}

update_proxy_config(){
  log 'Iniciando função update_proxy_config' "$YELLOW"
  # Atualizando Configurações do Proxy antes de atualizar os PDVs
  log "** Atualizando Configurações do Proxy antes de atualizar os PDVs" "$BLUE"
  sudo zabbix_proxy -R config_cache_reload
  sudo zabbix_proxy -R housekeeper_execute
}


# Função para verificar e adicionar o conteúdo ao arquivo CliSiTef.ini, se necessário
changeClisitef() {
    log 'Iniciando função changeClisitef' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local DISTRO="$4"
    local VERSION="$5"
    local ARCH="$6"
    local HOST="$7"

    # Define o comando SUDO_COMMAND de acordo com a distribuição
    if [ "$USER" != "root" ]; then 
      if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
        SUDO_COMMAND="echo '$PASS' | sudo -S"
      else
        SUDO_COMMAND="echo '$PASS' | su -c"
      fi
    else
      SUDO_COMMAND=""
    fi

    # Extrai o conteúdo do arquivo CliSiTef.ini para uma variável local
    local remote_file_content
    remote_file_content=$(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$USER@$IP" "cat /posnet/CliSiTef.ini" 2>/dev/null)
    if [ $? -ne 0 ]; then
        log "Erro ao acessar o arquivo remoto CliSiTef.ini" "$RED"
        return
    fi

    # Verifica se o conteúdo esperado está na variável local
    local add_salvaestado=false
    local add_diretoriobase=false

    if ! echo "$remote_file_content" | grep -q "^\[SalvaEstado\]"; then
        add_salvaestado=true
    fi
    if ! echo "$remote_file_content" | grep -q "^DiretorioBase=/posnet/"; then
        add_diretoriobase=true
    fi

    # Adiciona o conteúdo, se necessário
    if [ "$add_salvaestado" = true ] || [ "$add_diretoriobase" = true ]; then
        log "Adicionando conteúdo ao arquivo CliSiTef.ini" "$YELLOW"

        # Comando para garantir a quebra de linha final e adicionar o conteúdo
        local add_command=""
        add_command="${add_command}sudo sh -c 'tail -c1 /posnet/CliSiTef.ini | read -r _ || echo \"\" >> /posnet/CliSiTef.ini; "
        add_command="${add_command}echo \"\" >> /posnet/CliSiTef.ini; "  # Adiciona uma linha em branco

        # Adiciona as linhas necessárias ao final do arquivo
        if [ "$add_salvaestado" = true ]; then
            add_command="${add_command}echo \"[SalvaEstado]\" >> /posnet/CliSiTef.ini; "
        fi
        if [ "$add_diretoriobase" = true ]; then
            add_command="${add_command}echo \"DiretorioBase=/posnet/\" >> /posnet/CliSiTef.ini; "
        fi
        add_command="${add_command}'"

        # Executa o comando de adição remotamente
        run_sshpass "$SUDO_COMMAND $add_command" "$USER" "$PASS" "$IP"
        log "Conteúdo adicionado ao arquivo CliSiTef.ini com sucesso" "$GREEN"
    else
        log "Conteúdo já presente no arquivo CliSiTef.ini, nenhuma ação necessária" "$GREEN"
    fi
}






update_proxy_config

# Função para processar hosts a partir da resposta `host.get`
process_hosts_host_get() {
  local RESPONSE="$1"

  # Loop principal para processar os IPs e credenciais de acesso
  IFS=$'\n'
  for line in $(echo "$RESPONSE" | jq -c '.result[]'); do
    AVAILABLE=$(echo "$line" | jq -r '.interfaces[0].available')
    HOST=$(echo "$line" | jq -r '.host')
    IP=$(echo "$line" | jq -r '.interfaces[0].ip')
    PORT=$(echo "$line" | jq -r '.interfaces[0].port')
    USER_PASS=$(echo "$line" | jq -r '.inventory.notes')
    USER=$(echo "$USER_PASS" | cut -d',' -f1)
    PASS=$(echo "$USER_PASS" | cut -d',' -f2)

    process_host "$HOST" "$IP" "$PORT" "$USER" "$PASS" "$AVAILABLE"
  done
}


# Função para processar cada host
process_host() {
  local HOST="$1"
  local IP="$2"
  local PORT="$3"
  local USER="$4"
  local PASS="$5"
  local AVAILABLE="$6"

  log "Processando HOST: $HOST (IP $IP)"
  log "Status: $PARAM_AGENT_STATUS, AVAILABLE: $AVAILABLE"

  if [ -z "$USER" ] || [ -z "$PASS" ]; then
    log "Usuario ou Senha vazios" "$RED"
    return
  fi

  check_connection "$IP" "$USER" "$PASS"
  CONNECTION_STATUS=$?

  case $CONNECTION_STATUS in
    0)
      zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s $HOST -k pdv.credenciais_invalidas -o 0
      DISTRO_VERSION=$(detect_distro_and_version "$IP" "$USER" "$PASS")
      DISTRO=$(echo "$DISTRO_VERSION" | cut -d' ' -f1)
      VERSION=$(echo "$DISTRO_VERSION" | cut -d' ' -f2)
      ARCH=$(detect_architecture "$IP" "$USER" "$PASS")
      log "Conexão bem-sucedida com $IP"
      log "Distribuição: $DISTRO, Versão: $VERSION, Arquitetura: $ARCH" "$NC"

      if [ "$PARAM_CHANGE_CLISITEF" == 'true' ]; then
        changeClisitef "$USER" "$PASS" "$IP" "$DISTRO" "$VERSION" "$ARCH" "$HOST" "$PARAM_PROXY_IP" "$PORT"
      fi
      ;;
    1)
      log "Máquina não responde: $IP" "$RED" "$LOGFILE_MACHINE_UNRESPONSIVE"
      ;;
    2)
      log "Credenciais inválidas: $IP" "$RED" "$LOGFILE_INVALID_CREDENTIALS"
      zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s $HOST -k pdv.credenciais_invalidas -o 1
      ;;
  esac
  log "----------------------------"
}

JSON_REQ=$(cat <<EOF
{
"jsonrpc": "2.0",
"method": "host.get",
"params": {
"search": {
    "host": ["$PARAM_REDE-$filtro_host"]
},
"output": ["host"],
"selectInventory": ["notes"],
"selectInterfaces": ["ip", "port", "available"]
},
"auth": "$PARAM_TOKEN",
"id": 1
}
EOF
)
log "Conectando no Zabbix-Server"
RESPONSE=$(curl -k -s -X POST -H 'Content-Type: application/json-rpc' -d "$JSON_REQ" 'https://monitor.flagee.cloud/api_jsonrpc.php')
process_hosts_host_get "$RESPONSE"