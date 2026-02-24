#!/bin/bash


# Definindo códigos de cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variaveis globais
ARIUSMONITOR_CONFIG_FILE="/ariusmonitor/conf/zabbix_agentd.conf"
ARIUSMONITOR_CONFIG_PIDFILE="/ariusmonitor/logs/zabbix_agentd.pid"
ARIUSMONITOR_CONFIG_LOGFILE="/ariusmonitor/logs/zabbix_agentd.log"
ARIUSMONITOR_CONFIG_AGENTD_PATH="/ariusmonitor/conf/zabbix_agentd.conf.d/"
ARIUSMONITOR_CONFIG_INCLUDE="$ARIUSMONITOR_CONFIG_AGENTD_PATH*"
ARIUSMONTIOR_BOT_DIR="/ariusmonitor"


# Parametros shellscript
PARAM_PDV_IP=""
PARAM_SCRIPTS_PATH=""
PARAM_PDV=""
PARAM_AGENT_STATUS=""
PARAM_CREDENCIAIS_INVALIDAS="false"
PARAM_UPDATE_SAT="false"
PARAM_SAT_ASSOCIAR_ASSINATURA="false"
PARAM_CNPJ_CONTRIBUINTE=""
PARAM_CHAVE_ASSINATURA=""
PARAM_UPDATE_ARIUSMONITOR="false"
PARAM_UPDATE_ARIUSMONITOR_PARAM="false"
PARAM_REMOVE_MONITORASAT="false"
PARAM_FORCE_MONITORASAT="false"
PARAM_IGNORE_CONFIG_ARIUSMONITOR="false"
PARAM_INSTALL_FPING="false"
PARAM_MOVE_LOGS="false"
PARAM_DEBUG="false"
PARAM_BACKUP_CUPOM="false"
PARAM_SHUTDOWN="false"
PARAM_UNLOCK="false"
# Novo parâmetro para filtrar por hostid
PARAM_HOSTID=""
# Novo parâmetro para definir saída em JSON
PARAM_OUTPUT=""
INSTALL_STATUS="error"

# Carregue as variáveis do arquivo de configuração
source $ARIUSMONTIOR_BOT_DIR/config_bot.conf


# Analisando os parâmetros
TEMP=$(getopt -o h --long help,rede:,loja:,pdv:,hostid:,output:,pdv-ip:,agent-status:,credenciais-invalidas,cnpj-contribuinte:,chave-assinatura:,update-ariusmonitor,update-ariusmonitor-param,update-sat,remove-monitorasat,force-monitorasat,sat-associar-assinatura,ignore-config-ariusmonitor,install-fping,move-logs,debug,shutdown,backup-cupom,unlock -- "$@")
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
    --ignore-config-ariusmonitor)
      PARAM_IGNORE_CONFIG_ARIUSMONITOR="true"
      shift
      ;;
    --remove-monitorasat)
      PARAM_REMOVE_MONITORASAT="true"
      shift
      ;;
    --force-monitorasat)
      PARAM_FORCE_MONITORASAT="true"
      shift
      ;;   
    --update-ariusmonitor)
      PARAM_UPDATE_ARIUSMONITOR="true"
      shift
      ;;
    --update-ariusmonitor-param)
      PARAM_UPDATE_ARIUSMONITOR_PARAM="true"
      shift
      ;;
    --update-sat)
      PARAM_UPDATE_SAT="true"
      shift
      ;;
    --sat-associar-assinatura)
      PARAM_SAT_ASSOCIAR_ASSINATURA="true"
      shift
      ;;
    --cnpj-contribuinte)
      PARAM_CNPJ_CONTRIBUINTE="$2"
      shift 2
      ;;
    --chave-assinatura)
      PARAM_CHAVE_ASSINATURA="$2"
      shift 2
      ;;
    --install-fping)
      PARAM_INSTALL_FPING="true"
      shift
      ;;
    --move-logs)
      PARAM_MOVE_LOGS="true"
      shift
      ;;
    --debug)
      PARAM_DEBUG="true"
      shift
      ;;
    --shutdown)
      PARAM_SHUTDOWN="true"
      shift
      ;;
    --backup-cupom)
      PARAM_BACKUP_CUPOM="true"
      shift
      ;;
    --unlock)
      PARAM_UNLOCK="true"
      shift
      ;;
    --hostid)
      PARAM_HOSTID="$2"
      shift 2
      ;;
    --output)
      PARAM_OUTPUT="$2"
      shift 2
      ;;
    --help)
      echo -e "$GREE Todos os Direitos Reservados a Flagee.Cloud $NC"
      echo ""
      echo -e "$BLUE PDV - ATUALIZAR MONITORAMENTO $NC"
      echo " Atualizar todas as Lojas:                 ./bot_ariusmonitor"
      echo " Atualizar Loja:                           ./bot_ariusmonitor --loja <LOJA001>"
      echo " Atualizar PDV por Nome:                   ./bot_ariusmonitor --loja <LOJA001> --pdv <PDV201>"
      echo " Atualizar PDV por IP:                     ./bot_ariusmonitor --pdv-ip <0.0.0.0>"
      echo " Parametros de apoio:                      --move-logs (move os logs em /posnet para /posnet/logs_old)"
      echo " Parametros de apoio:                      --update-ariusmonitor (atualiza o agente do zabbix)"
      echo " Parametros de apoio:                      --agent-status (filtra hosts por status no zabbix: 0 - interface indisponivel, 2 - ok, 2 - falha)"
      echo ""
      echo -e "$BLUE SAT - ATUALIZAR SOFTWARE $NC"
      echo " Atualizar SAT por Loja:                   ./bot_ariusmonitor --loja <LOJA001> --sat-update"
      echo " Atualizar SAT por Nome do PDV:            ./bot_ariusmonitor --loja <LOJA001> --pdv <PDV201> --sat-update"
      echo " Atualizar SAT por IP do PDV:              ./bot_ariusmonitor --pdv-ip <0.0.0.0> --sat-update"
      echo ""
      echo -e "$BLUE SAT - ASSOCIAR ASSINATURA $NC"
      echo " Associar Assinatura por Loja:             ./bot_ariusmonitor --loja <LOJA001> --sat-associar-assinatura --cnpj-contribuinte <CNPJ CONTRIBUINTE> --chave-assinatura \"<CHAVE ASSINATURA>\""
      echo " Associar Assinatura por Nome do PDV:      ./bot_ariusmonitor --loja <LOJA001> --pdv <PDV201> --sat-associar-assinatura --cnpj-contribuinte <CNPJ CONTRIBUINTE> --chave-assinatura \"<CHAVE ASSINATURA>\""
      echo " Associar Assinatura por IP do PDV:        ./bot_ariusmonitor --pdv-ip <0.0.0.0> --sat-associar-assinatura --cnpj-contribuinte <CNPJ CONTRIBUINTE> --chave-assinatura \"<CHAVE ASSINATURA>\""
      echo ""
      echo -e "$YELLOW Importante: o valor do parâmetro --chave-assinatura deve ser entre aspas $NC"
      exit 1
      ;;
    --)
      shift
      break
      ;;
  esac
done

# Define o arquivo de bloqueio
LOCKFILE="/tmp/bot_ariusmonitor.lock"

# Verifica se o arquivo de bloqueio existe
if [ -e "$LOCKFILE" ] && [ $PARAM_UNLOCK == 'false' ]; then
    # O arquivo de bloqueio existe, o que significa que outra instância pode estar em execução
    echo "Outro processo do bot_ariusmonitor está em execução."
    echo "Para matar o processo, remova o arquivo de bloqueio $LOCKFILE ou use 'pkill -f bot_ariusmonitor.sh'"
    exit 1
else
    # Cria o arquivo de bloqueio para indicar que este processo está em execução
    touch "$LOCKFILE"
    # Garante que o arquivo de bloqueio será removido ao sair do script, mesmo após uma interrupção
    trap "rm -f $LOCKFILE" EXIT
fi


if [ "$PARAM_OUTPUT" = "json" ]; then
  QUIET_JSON=true
else
  QUIET_JSON=false
fi

if [ "$QUIET_JSON" = false ]; then
  echo -e "${BLUE}LOJA: ${PARAM_REDE} - PROXY: ${PARAM_PROXY_IP}${NC}" >&2
fi

# Definir arquivos de log
LOGFILE_GENERAL="/ariusmonitor/logfile_general.log"
LOGFILE_INVALID_CREDENTIALS="/ariusmonitor/logfile_invalid_credentials.log"
LOGFILE_MONITORASAT="/ariusmonitor/logfile_monitorasat.log"
LOGFILE_HTCONFIG_NOTINSTALLED="/ariusmonitor/logfile_htcconfig_notinstalled.log"
LOGFILE_MACHINE_UNRESPONSIVE="/ariusmonitor/logfile_machine_unresponsive.log"


# Função para registrar LOG
log() {
  local MESSAGE="$1"
  local COLOR="${2:-$NC}"
  local LOGFILE="$3"

  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

  # sempre grava em arquivo de log
  echo -e "${TIMESTAMP} - ${MESSAGE}" >> "$LOGFILE_GENERAL"
  [ -n "$LOGFILE" ] && echo -e "${TIMESTAMP} - ${MESSAGE}" >> "$LOGFILE"

  # só imprime na tela se NÃO estivermos em modo JSON
  if [ "$QUIET_JSON" = false ]; then
    # enviando para stderr pra não poluir o stdout
    echo -e "${COLOR}${TIMESTAMP} - ${MESSAGE}${NC}" >&2
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

# antes de montar JSON_REQ:
if [ -n "$PARAM_HOSTID" ]; then
  # se passar hostid, retorna só esse host
  JSON_FILTER=$(cat <<-EOF
    "hostids":["$PARAM_HOSTID"]
EOF
  )
elif [ -n "$PARAM_LOJA" ] && [ -n "$PARAM_PDV" ]; then
  JSON_FILTER=$(cat <<-EOF
    "search":{"host":["$PARAM_REDE-$PARAM_LOJA-$PARAM_PDV"]}
EOF
  )
elif [ -n "$PARAM_LOJA" ]; then
  JSON_FILTER=$(cat <<-EOF
    "search":{"host":["$PARAM_REDE-$PARAM_LOJA"]}
EOF
  )
elif [ -n "$PARAM_PDV_IP" ]; then
  JSON_FILTER=$(cat <<-EOF
    "filter":{"ip":"$PARAM_PDV_IP"}
EOF
  )
else
  JSON_FILTER=$(cat <<-EOF
    "search":{"host":["$PARAM_REDE"]}
EOF
  )
fi

log "###### Iniciando Bot Arius Monitor para $PARAM_REDE $PARAM_LOJA $PARAM_PDV $PARAM_PDV_IP" "$GREEN"


#### FIM DA CHECAGEM DE PARÂMETROS ####




# Função para verificar a conectividade com a máquina de destino
check_connection() {
  local IP="$1"
  local USER="$2"
  local PASS="$3"
  local PORT_SSH="$4"

  # 1) Teste TCP
  timeout 5 bash -c "echo >/dev/tcp/$IP/$PORT_SSH" >/dev/null 2>&1 || return 1  # sem conexão TCP

  # 2) SSH direto, SEM checar ou gravar em known_hosts
  local SSH_OPTS=(-p "$PORT_SSH"
                  -o PreferredAuthentications=password
                  -o PubkeyAuthentication=no
                  -o StrictHostKeyChecking=no
                  -o UserKnownHostsFile=/dev/null
                  -o ConnectTimeout=5)
  OUTPUT=$(timeout 30 sshpass -p "$PASS" ssh "${SSH_OPTS[@]}" "$USER@$IP" "true" 2>&1)
  local STATUS=$?

  # 3) Interpreta retorno
  if [ $STATUS -eq 124 ]; then
    return 3   # timeout SSH
  elif echo "$OUTPUT" | grep -q "Permission denied"; then
    return 2   # credenciais inválidas
  elif [ $STATUS -ne 0 ]; then
    return 4   # outro erro qualquer
  fi

  return 0     # OK
}



# Função para detectar a distribuição e a versão do Linux na máquina de destino
detect_distro_and_version() {
  local IP="$1"
  local USER="$2"
  local PASS="$3"

  # Verifica se o comando lsb_release está disponível
  LSB_RELEASE_EXISTS=$(timeout 30 sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "which lsb_release 2>&1 | grep -v 'no lsb_release' | wc -l")

  if [ "$LSB_RELEASE_EXISTS" = "1" ]; then
    # Utilize o lsb_release para identificar a distribuição e versão
    DISTRO_INFO=$(timeout 30 sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "lsb_release -a 2>/dev/null")
  else
    # Tratamento alternativo para Slackware
    DISTRO_INFO=$(timeout 30 sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "cat /etc/slackware-version 2>/dev/null")
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

  ARCHITECTURE=$(timeout 30 sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "uname -m" 2>/dev/null)

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

get_ariusmonitor_geral_config(){
  log "Atualizando arquivo geral.conf"
  wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/geral.conf" --no-check-certificate >/dev/null 2>&1
  
  log "Atualizando arquivo ariusmonitor.tar.gz"
  wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/ariusmonitor.tar.gz" --no-check-certificate >/dev/null 2>&1
  
  #log "Atualizando arquivo MonitoraSATc"
  #wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/MonitoraSATc" --no-check-certificate >/dev/null 2>&1
  
  #log "Atualizando arquivo MonitoraSATc64"
  #wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/MonitoraSATc64" --no-check-certificate >/dev/null 2>&1
  
  #log "Atualizando arquivo MonitoraSAT.sh"
  #wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/MonitoraSAT.sh" --no-check-certificate >/dev/null 2>&1

  log "Atualizando arquivo libs.tar.gz"
  wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/libs.tar.gz" --no-check-certificate >/dev/null 2>&1
  
  #log "Atualizando arquivo certi_api.pem"
  #wget -N -P "$ARIUSMONTIOR_BOT_DIR" "https://ariusmonitor-repo.flagee.cloud/certi_api.pem" --no-check-certificate >/dev/null 2>&1
  
  #if [ "$PARAM_SCRIPTS_PATH" != "" ]; then
  #  log "Atualizando scripts $PARAM_SCRIPTS_PATH/scripts.tar.gz"
  #  wget -N -P "$ARIUSMONTIOR_BOT_DIR/$PARAM_SCRIPTS_PATH" "https://ariusmonitor-repo.flagee.cloud/$PARAM_SCRIPTS_PATH/scripts.tar.gz" --no-check-certificate >/dev/null 2>&1
  #fi

  # Ajustando permissões dos arquivos MonitoraSATC e MonitoraSAT.sh
  #log "Ajustando permissões dos arquivos MonitoraSATC e MonitoraSAT.sh"
  #chmod 777 $ARIUSMONTIOR_BOT_DIR/MonitoraSATc $ARIUSMONTIOR_BOT_DIR/MonitoraSATc64 $ARIUSMONTIOR_BOT_DIR/MonitoraSAT.sh
}

# Define uma função auxiliar para executar comandos sshpass,
# suportando senhas com caracteres especiais
run_sshpass() {
    local cmd="$1"              # comando remoto a ser executado
    local USER="$2"             # usuário SSH
    local PASS="$3"             # senha (pode conter espaços, #, $, etc.)
    local IP="$4"               # IP ou hostname remoto
    local DEBUG_INDIVIDUAL="$5" # se true, log extra no arquivo específico
    local PORT_SSH="$6"         # porta SSH

    # Monta o comando em um array para evitar reexpansão de variáveis
    local args=(timeout 30 sshpass -p "$PASS" ssh -p "$PORT_SSH" -T -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "$cmd")

    # Executa o array diretamente; a senha não será interpretada pelo shell
    local output
    output="$("${args[@]}" 2>&1)"
    local exit_status=$?

    # Logs em modo debug geral
    if [ "${PARAM_DEBUG:-false}" = "true" ]; then
        log "Comando: ${args[*]}"
        log "Saída: $YELLOW$output$NC"
        log "Status de saída: $exit_status"
    fi

    # Logs em modo debug individual (específico para monitorasat, por ex.)
    if [ "$DEBUG_INDIVIDUAL" = "true" ]; then
        log "Comando: ${args[*]}"
        log "**** Retorno: $YELLOW$output$NC" "" "$LOGFILE_MONITORASAT"
    fi

    if [ $exit_status -ne 0 ]; then
        log "Falha ao executar o comando: ${args[*]}"
    fi
}




# Define uma função auxiliar para executar comandos scp com sshpass, 
# suportando senhas especiais sem precisar escapar manualmente.
run_sshpass_scp() {
    local ORIGEM="$1"      # caminho do arquivo local a ser copiado
    local DESTINO="$2"     # caminho de destino remoto (relative a BASE_DESTINO)
    local USER="$3"        # usuário remoto
    local PASS="$4"        # senha do usuário remoto (pode conter #, $, espaços...)
    local IP="$5"          # IP do servidor remoto
    local PORT_SSH="$6"    # porta SSH no servidor remoto

    # Se DESTINO não estiver vazio, define BASE_DESTINO como "~/" (home do usuário remoto)
    local BASE_DESTINO=""
    if [ -n "$DESTINO" ]; then
        BASE_DESTINO="~/"
    fi

    scp_opts=( -P "$PORT_SSH"
           -o StrictHostKeyChecking=no
           -o UserKnownHostsFile=/dev/null
           -o ConnectTimeout=60
           -o ServerAliveInterval=10
           -o ServerAliveCountMax=5 )

    # Monta o comando em um array para evitar problemas de "expansão de variáveis".
    # Cada elemento do array será passado como argumento literal para o comando final.
    local args=(timeout 30 sshpass -p "$PASS" scp "${scp_opts[@]}" "$ORIGEM" "$USER@$IP:$BASE_DESTINO$DESTINO")

    # Executa o array. O Bash jamais reexpande $PASS (contendo #$, etc.), pois 
    # estamos passando cada parte como elemento literal em "${args[@]}".
    local output
    output="$("${args[@]}" 2>&1)"
    local exit_status=$?

    # Se estiver em modo debug, exibe o comando completo e a saída.
    if [ "${PARAM_DEBUG:-false}" = "true" ]; then
        # A variável ${args[*]} junta os elementos separados por espaço para exibição.
        log "Comando: ${args[*]}"
        log "Saída: $YELLOW$output$NC"
        log "Status de saída: $exit_status"
    fi

    if [ $exit_status -ne 0 ]; then
        log "Falha ao executar o comando: ${args[*]}"
    fi
}




# update_zabbix_geral_config(){}

# Função para verificar a instalação do monitoramento
check_installation() {
  log 'Iniciando função check_installation' "$YELLOW"
  local USER="$1"
  local PASS="$2"
  local IP="$3"
  local DISTRO="$4"
  local VERSION="$5"
  local ARCH="$6"
  local HOST="$7"
  local IP_PROXY="$8"
  local PORT_ZABBIX="$9"
  local PORT_SSH="${10}"

  # Define o comando SUDO_COMMAND de acordo com a distribuição
  if [ $USER != "root" ]; then 
    if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
      SUDO_COMMAND="echo '$PASS' | sudo -S"
    else
      SUDO_COMMAND="echo '$PASS' | su -c"
    fi
  else
    SUDO_COMMAND=""
  fi


  # Verifica se o pacote 'ariusmonitor' está instalado
  ARIUSMONITOR_AGENT_INSTALLED=$(sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "ls /ariusmonitor/conf/zabbix_agentd.conf 2>/dev/null" 2>/dev/null)


  # Instala ou atualiza o ariusmonitor-agent
  if [ -z "$ARIUSMONITOR_AGENT_INSTALLED" ] || [ $PARAM_UPDATE_ARIUSMONITOR == 'true' ]; then
    # Instalando novo ariusmonitor-agent
    log "** Instalando novo ariusmonitor-agent" "$GREEN"
    install_package_ariusmonitor "$USER" "$PASS" "$IP" "$SUDO_COMMAND" "$DISTRO" "$VERSION" "$ARCH" "$HOST" "$IP_PROXY" "$PORT_ZABBIX" "$PORT_SSH"
  else
    if [ $PARAM_IGNORE_CONFIG_ARIUSMONITOR == 'false' ]; then
      log "** ariusmonitor-agent encontrado" "$BLUE"
      # Atualizando ariusmonitor-agent
      log "** Atualizando configurações do ariusmonitor-agent - $PORT_SSH"
      update_ariusmonitor_agent_config "$USER" "$PASS" "$IP" "$SUDO_COMMAND" "$IP_PROXY" "$HOST" "$DISTRO" "$VERSION" "$PORT_ZABBIX" "$PORT_SSH"
    else 
      log "** ariusmonitor-agent encontrado" "$BLUE"
      log "** Ignorando atualização do ariusmonitor"
    fi
  fi


}


update_proxy_config(){
  log 'Iniciando função update_proxy_config' "$YELLOW"
  # Atualizando Configurações do Proxy antes de atualizar os PDVs
  log "** Atualizando Configurações do Proxy antes de atualizar os PDVs" "$BLUE"
  sudo zabbix_proxy -R config_cache_reload >/dev/null 2>&1
  sudo zabbix_proxy -R housekeeper_execute >/dev/null 2>&1
}



# Função para atualizar a configuração do 'ariusmonitor-agent'
update_ariusmonitor_agent_config() {
  log 'Iniciando função update_ariusmonitor_agent_config' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local SUDO_COMMAND="$4"
    local IP_PROXY="$5"
    local HOST="$6"
    local DISTRO="$7"
    local VERSION="$8"
    local PORT_ZABBIX="$9"
    local PORT_SSH="${10}"
    local ALLOWROOT=1
    local MAXLINEPERSECOND=100
    
    local BASE_DESTINO="~"

    # Enviando arquivo MonitoraSATc
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/MonitoraSATc - $USER $PASS $IP $PORT_SSH"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraSATc" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/MonitoraSATc /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Enviando arquivo MonitoraSATc64
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraSATc64"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraSATc64" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/MonitoraSATc64 /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Enviando arquivo MonitoraSAT.sh
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraSAT.sh"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraSAT.sh" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/MonitoraSAT.sh /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Enviando arquivo MonitoraImpressora
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraImpressora"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/MonitoraImpressora" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/MonitoraImpressora /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Enviando arquivo libs.tar.gz
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/libs.tar.gz"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/libs.tar.gz" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/libs.tar.gz /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    log "** Descompactando /ariusmonitor/libs.tar.gz"
    run_sshpass "$SUDO_COMMAND tar zxvf /ariusmonitor/libs.tar.gz -C /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    if [ "$PARAM_SCRIPTS_PATH" != "" ]; then
      # Enviando arquivo scripts.tar.gz
      log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/scripts.tar.gz"
      run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/scripts.tar.gz" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
      run_sshpass "$SUDO_COMMAND mv ~/scripts.tar.gz /ariusmonitor/scripts.tar.gz" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    
      log "** Descompactando /ariusmonitor/scripts.tar.gz"
      run_sshpass "$SUDO_COMMAND tar zxvf /ariusmonitor/scripts.tar.gz -C /ariusmonitor/" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    fi

    # log "** Removendo arquivo /ariusmonitor/sat.conf"
    # run_sshpass "$SUDO_COMMAND rm /ariusmonitor/sat.conf" "$USER" "$PASS" "$IP"

    # Enviando arquivo geral.conf
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/geral.conf"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/geral.conf" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/geral.conf $ARIUSMONITOR_CONFIG_AGENTD_PATH" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    log "** Executando /ariusmonitor/utilities/update.sh"
    run_sshpass "$SUDO_COMMAND /ariusmonitor/utilities/update.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Recriando arquivo $ARIUSMONITOR_CONFIG_FILE.. DEIXAR SEM IDENTAR A PARTE DO CAT
    log "** Recriando arquivo $ARIUSMONITOR_CONFIG_FILE"
    run_sshpass "$SUDO_COMMAND bash -c 'cat << EOF > $ARIUSMONITOR_CONFIG_FILE
Server=$IP_PROXY
ServerActive=$IP_PROXY
ListenPort=$PORT_ZABBIX
LogFile=$ARIUSMONITOR_CONFIG_LOGFILE
PidFile=$ARIUSMONITOR_CONFIG_PIDFILE
Hostname=$HOST
BufferSize=300
AllowRoot=1
Include=$ARIUSMONITOR_CONFIG_INCLUDE
MaxLinesPerSecond=50
AllowKey=system.run[*]
UnsafeUserParameters=1
Timeout=20
EOF'" $USER $PASS $IP "" $PORT_SSH


    if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
      # Configurando SUDOER para executar MonitoraSAT
      log "** Configurando SUDOER para executar MonitoraSAT"
      run_sshpass "$SUDO_COMMAND bash -c 'cat << EOF > /etc/sudoers.d/ariusmonitor
ariusmonitor ALL = NOPASSWD: /ariusmonitor/MonitoraSAT.sh
ariusmonitor ALL = NOPASSWD: /ariusmonitor/MonitoraSATc
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill MonitoraSATc
ariusmonitor ALL = NOPASSWD: /bin/bash -c /ariusmonitor/MonitoraSATc
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill -f MonitoraSATc
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill -f /ariusmonitor/zabbix/sbin/zabbix_agentd
ariusmonitor ALL = NOPASSWD: /usr/bin/pgrep -x MonitoraSATc
ariusmonitor ALL = NOPASSWD: /ariusmonitor/MonitoraSATc64
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill MonitoraSATc64
ariusmonitor ALL = NOPASSWD: /bin/bash -c /ariusmonitor/MonitoraSATc64
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill -f MonitoraSATc64
ariusmonitor ALL = NOPASSWD: /usr/bin/pgrep -x MonitoraSATc64
ariusmonitor ALL = NOPASSWD: /usr/bin/crontab -l -u root

ariusmonitor ALL = NOPASSWD: /bin/grep *SalvaEstado* /posnet/CliSiTef.ini
ariusmonitor ALL = NOPASSWD: /bin/grep *DiretorioBase=/posnet/* /posnet/CliSiTef.ini

# Permitir acesso às bibliotecas específicas
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libsatprotocol.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libSAT.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libsattanca.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libSatGer.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libbemasat.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libsatelgin.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libsatelgin-linker2.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /posnet/libsatid.so
ariusmonitor ALL = NOPASSWD: /usr/bin/readelf -h /home/arius/AriusIntegrador/libsat.so
EOF'" $USER $PASS $IP "" $PORT_SSH
    fi

    if [[ "$PARAM_SAT_ASSOCIAR_ASSINATURA" == 'true' && ( "$PARAM_LOJA" != '' || "$PARAM_PDV_IP" != '' ) ]]; then
      
      if [[ "$PARAM_CNPJ_CONTRIBUINTE" == '' || "$PARAM_CHAVE_ASSINATURA" == '' ]]; then
        log "** Para associar uma assinatura ao SAT, informe os valores dos parâmetros --cnpj-contribuinte e --chave-assinatura" "$RED" "$LOGFILE_MONITORASAT"
      else
        log "** Iniciando Associação de Assinatura do SAT no PDV $HOST" "$GREEN" "$LOGFILE_MONITORASAT"
        run_sshpass "$SUDO_COMMAND /ariusmonitor/MonitoraSAT.sh --func AssociarAssinatura --cnpj-contribuinte $PARAM_CNPJ_CONTRIBUINTE --chave \"$PARAM_CHAVE_ASSINATURA\"" "$USER" "$PASS" "$IP" "true" "$PORT_SSH"
      fi
    elif [[ "$PARAM_SAT_ASSOCIAR_ASSINATURA" == 'true' && ( "$PARAM_LOJA" == '' && "$PARAM_PDV_IP" == '' ) ]]; then
      log "** Para associar uma assinatura ao SAT, informe um valor para --loja ou --pdv-ip" "$RED" "$LOGFILE_MONITORASAT"
    fi


    if [ "$PARAM_UPDATE_SAT" == 'true' ]; then
      log "** Iniciando Atualização do SAT no PDV $HOST" "$GREEN" "$LOGFILE_MONITORASAT"
      run_sshpass "$SUDO_COMMAND /ariusmonitor/MonitoraSAT.sh --func AtualizarSoftwareSAT" "$USER" "$PASS" "$IP" "true" "$PORT_SSH"
    fi

    log "** Reiniciando o serviço do ariusmonitor-agent"
    run_sshpass "$SUDO_COMMAND /ariusmonitor/utilities/start.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    log "** Enviando trapper ligado=1"
    run_sshpass "$SUDO_COMMAND /ariusmonitor/zabbix/bin/zabbix_sender -c $ARIUSMONITOR_CONFIG_FILE -k ligado -o 1" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    INSTALL_STATUS="ok"

}

    
# Função para instalar o pacote no Ubuntu
install_package_ariusmonitor() {
    log 'Iniciando função install_package_ariusmonitor' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local SUDO_COMMAND="$4"
    local DISTRO="$5"
    local VERSION="$6"
    local ARCH="$7"
    local HOST="$8"
    local IP_PROXY="$9"
    local PORT_ZABBIX="${10}"
    local PORT_SSH="${11}"

    PACKAGE_FILE="ariusmonitor.tar.gz"
    PACKAGE_PATH="/ariusmonitor/ariusmonitor.tar.gz"

    # Verifica se o arquivo do pacote existe
    if [ ! -e "$PACKAGE_PATH" ]; then
        log "** Pacote não encontrado $PACKAGE_PATH"
        return
    fi

    if [ $PARAM_MOVE_LOGS == 'true' ]; then
      log "** Movendo logs antigos do Arius PDV para a pasta /posnet/logs_old/"
      run_sshpass "$SUDO_COMMAND mkdir /posnet/logs_old/" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
      run_sshpass "$SUDO_COMMAND find /posnet -maxdepth 1 -name 'log*.txt' -type f -mtime +1 -exec mv {} /posnet/logs_old/ \;" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
      run_sshpass "$SUDO_COMMAND find /posnet -maxdepth 1 -name 'nfiscal*.txt' -type f -mtime +1 -exec mv {} /posnet/logs_old/ \;" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    fi

    local BASE_DESTINO="~"

    # Inicia o envio do pacote
    log "** Enviando pacote $PACKAGE_FILE para $IP" "$NC" "$LOGFILE_HTCONFIG_NOTINSTALLED"
    run_sshpass_scp "$PACKAGE_PATH" "" "$USER" "$PASS" "$IP" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND rm -f /ariusmonitor.tar.gz >/dev/null 2>&1" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv $BASE_DESTINO/$PACKAGE_FILE /" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Verifica se o envio do pacote foi bem sucedido
    if [ $? -eq 0 ]; then
        log "** Descompactando $PACKAGE_FILE no $DISTRO $VERSION"
        run_sshpass "$SUDO_COMMAND tar zxvf /$PACKAGE_FILE -C /" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

        log "** Parando serviço $PACKAGE_FILE no $DISTRO $VERSION"
        run_sshpass "$SUDO_COMMAND /ariusmonitor/utilities/stop.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

        log "** Instalando pacote ariusmonitor no $DISTRO $VERSION"
        run_sshpass "$SUDO_COMMAND /ariusmonitor/utilities/setup.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

        if [ $? -eq 0 ]; then
          log "** ariusmonitor instalado com sucesso" "$GREEN"
        else
          log "** Falha ao instalar ariusmonitor" "$RED"
        fi
        
        # Atualiza as configurações do ariusmonitor-agent
        log "** Atualizando configurações do ariusmonitor-agent - $PORT_SSH"
        update_ariusmonitor_agent_config "$USER" "$PASS" "$IP" "$SUDO_COMMAND" "$IP_PROXY" "$HOST" "$DISTRO" "$VERSION" "$PORT_ZABBIX" "$PORT_SSH"
    fi
    
}


# Função para instalar o pacote no Ubuntu
remove_monitorasat() {
    log 'Iniciando função remove_monitorasat' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local DISTRO="$4"
    local VERSION="$5"
    local ARCH="$6"
    local HOST="$7"
    local IP_PROXY="$8"
    local PORT_SSH="$9"

    # Define o comando SUDO_COMMAND de acordo com a distribuição
    if [ $USER != "root" ]; then 
      if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
        SUDO_COMMAND="echo '$PASS' | sudo -S"
      else
        SUDO_COMMAND="echo '$PASS' | su -c"
      fi
    else
      SUDO_COMMAND=""
    fi

    # Inicia o envio do pacote
    log "** Removendo MonitoraSAT para $IP" "$NC" "$LOGFILE_HTCONFIG_NOTINSTALLED"
    run_sshpass "$SUDO_COMMAND rm -f /ariusmonitor/MonitoraSATc" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND rm -f /ariusmonitor/MonitoraSATc64" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND rm -f /ariusmonitor/MonitoraSAT" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND rm -f /ariusmonitor/MonitoraSAT.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
}


# Função para instalar o pacote no Ubuntu
force_monitorasat() {
    log 'Iniciando função force_monitorasat' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local DISTRO="$4"
    local VERSION="$5"
    local ARCH="$6"
    local HOST="$7"
    local IP_PROXY="$8"
    local PORT_ZABBIX="$9"
    local PORT_SSH="${10}"

    # Define o comando SUDO_COMMAND de acordo com a distribuição
    if [ $USER != "root" ]; then 
      if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
        SUDO_COMMAND="echo '$PASS' | sudo -S"
      else
        SUDO_COMMAND="echo '$PASS' | su -c"
      fi
    else
      SUDO_COMMAND=""
    fi
    # Enviando arquivo libs.tar.gz
    log "** Enviando arquivo $ARIUSMONTIOR_BOT_DIR/host-linux/libs.tar.gz"
    run_sshpass_scp "$ARIUSMONTIOR_BOT_DIR/host-linux/libs.tar.gz" "" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    run_sshpass "$SUDO_COMMAND mv ~/libs.tar.gz /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    log "** Descompactando /ariusmonitor/libs.tar.gz"
    run_sshpass "$SUDO_COMMAND tar zxvf /ariusmonitor/libs.tar.gz -C /ariusmonitor" "$USER" "$PASS" "$IP" "" "$PORT_SSH"

    # Inicia o envio do pacote
    log "** Forçando MonitoraSAT para $IP" "$NC" "$LOGFILE_HTCONFIG_NOTINSTALLED"
    run_sshpass "$SUDO_COMMAND /ariusmonitor/MonitoraSAT.sh" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
}


# Função para realizar backup dos cupons XML dos últimos 10 dias
backup_cupom() {
    log 'Iniciando função backup_cupom' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local HOST="$4"
    local PORT_SSH="$5"
    local BASE_DIR="/posnet/NFCEBKP/"  # Diretório base no host de origem
    local DEST_DIR="/NFCEBKP/$HOST/"  # Diretório de destino no host intermediário
    

    # Exportar senha para sshpass
    export SSHPASS=$PASS

    # Comando SSH para listar subdiretórios dentro de NFCEBKP (representando CNPJs)
    local SSH_CMD="sshpass -e ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null -l $USER $IP"
    local CNPJs=$(eval "$SSH_CMD ls $BASE_DIR")

    # Iterar sobre cada CNPJ e verificar diretórios de datas
    for CNPJ in $CNPJs; do
        local DATES=()
        for i in {0..9}; do
            DATES+=($(date --date="$i days ago" +%Y-%m-%d))
        done
        
        for DATE in "${DATES[@]}"; do
            local CURRENT_DIR="${BASE_DIR}${CNPJ}/${DATE}/"
            local EXISTS_CMD="$SSH_CMD test -d \"$CURRENT_DIR\" && echo exists"
            if [ "$(eval $EXISTS_CMD)" == "exists" ]; then

                scp_opts=( -P "$PORT_SSH"
                  -o StrictHostKeyChecking=no
                  -o UserKnownHostsFile=/dev/null
                  -o ConnectTimeout=60
                  -o ServerAliveInterval=10
                  -o ServerAliveCountMax=5 )

                local FULL_DEST_DIR="$DEST_DIR$CNPJ/$DATE/"
                mkdir -p "$FULL_DEST_DIR"
                # Ajustar o comando para copiar o conteúdo do diretório, não o diretório
                local SCP_CMD="sshpass -p '$PASS' scp "${scp_opts[@]}" $USER@$IP:\"$CURRENT_DIR*\" \"$FULL_DEST_DIR\""
                log "Executando backup de arquivos XML de $DATE para $HOST no CNPJ $CNPJ"
                eval $SCP_CMD
                if [ $? -eq 0 ]; then
                    log "Backup de $DATE no CNPJ $CNPJ bem-sucedido para $HOST" "$GREEN"
                else
                    log "Erro ao realizar backup de $DATE no CNPJ $CNPJ para $HOST" "$RED"
                fi
            else
                log "Diretório $DATE não existe para CNPJ $CNPJ em $HOST, pulando..." "$YELLOW"
            fi
        done
    done

    # Limpar variável de ambiente
    unset SSHPASS
}

# Função para realizar o desligamento de máquinas com condicionamento de horário
shutdown() {
    log 'Iniciando função shutdown' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local DISTRO="$4"
    local VERSION="$5"
    local ARCH="$6"
    local HOST="$7"
    local PORT_SSH="$8"

    # Define o comando SUDO_COMMAND de acordo com a distribuição
    if [ $USER != "root" ]; then 
      if [ "$DISTRO" = "Ubuntu" ] || [ "$DISTRO" = "Mint" ]; then
        SUDO_COMMAND="echo '$PASS' | sudo -S"
      else
        SUDO_COMMAND="echo '$PASS' | su -c"
      fi
    else
      SUDO_COMMAND=""
    fi

    # Obtém a hora atual no formato de 24 horas (HH)
    local hour=$(date +%H)  # Obtem a hora atual do sistema no formato de 24 horas.
    
    # Converte a hora para número inteiro para comparação
    local HOUR=$(echo $CURRENT_HOUR | sed 's/^0*//')

    # Verifica se a hora atual está entre 23 e 5 (inclui 23, mas não 7)
    if [ "$hour" -ge 23 ] || [ "$hour" -le 5 ]; then
        log "Desligando $HOST" "$YELLOW"
        run_sshpass "$SUDO_COMMAND shutdown -h now" "$USER" "$PASS" "$IP" "" "$PORT_SSH"
    else
        log "Fora do horário de desligamento automático para $HOST" "$YELLOW"
        exit 1
    fi
}

# Função para verificar se o ariusmonitor-agent foi instalado
check_ariusmonitor_agent_installed() {
    log 'Iniciando função check_ariusmonitor_agent_installed' "$YELLOW"
    local USER="$1"
    local PASS="$2"
    local IP="$3"
    local PORT_SSH="$4"
    
    ZABBIX_AGENT_INSTALLED=$(timeout 30 sshpass -p "$PASS" ssh -p $PORT_SSH -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-dss -o UserKnownHostsFile=/dev/null "$USER@$IP" "which ariusmonitor" 2>/dev/null)
    if [ -n "$ZABBIX_AGENT_INSTALLED" ]; then
        log "** ariusmonitor-agent instalado com sucesso" "$GREEN"
    else
        log "** Falha ao instalar ariusmonitor-agent" "$RED"
    fi
}

update_proxy_config
get_ariusmonitor_geral_config

# Função para processar hosts a partir da resposta `host.get`
process_hosts_host_get() {
  local RESPONSE="$1"

  # Verifica se a resposta contém o campo 'result'
  if ! echo "$RESPONSE" | jq -e '.result' >/dev/null; then
    log "❌ Erro ao consultar a API Zabbix. Resposta inválida:" "$RED"
    echo "$RESPONSE"
    return 1
  fi

  IFS=$'\n'
  for line in $(echo "$RESPONSE" | jq -c '.result[]'); do
    # Verifica se 'interfaces' não é null
    INTERFACES=$(echo "$line" | jq -r '.interfaces')
    INVENTORY=$(echo "$line" | jq -r '.inventory')

    if [[ "$INTERFACES" == "null" || "$INVENTORY" == "null" ]]; then
      log "Host com dados incompletos, ignorando..." "$YELLOW"
      continue
    fi

    AVAILABLE=$(echo "$line" | jq -r '.interfaces[0].available // empty')
    HOST=$(echo "$line" | jq -r '.host')
    IP=$(echo "$line" | jq -r '.interfaces[0].ip // empty')
    PORT_ZABBIX=$(echo "$line" | jq -r '.interfaces[0].port // empty')
    #USER_PASS=$(echo "$line" | jq -r '.inventory.notes // ","')
    #USER=$(echo "$USER_PASS" | cut -d',' -f1)
    #PASS=$(echo "$USER_PASS" | cut -d',' -f2)

    USER_PASS=$(echo "$line" | jq -r '.inventory.notes // ""')
    # Divide em 3 campos: USER, PASS e, opcionalmente, PORT_SSH
    IFS=',' read -r USER PASS PORT_SSH <<< "$USER_PASS"
    # Se não houver terceira posição (PORT_SSH), define 22 como padrão
    if [ -z "$PORT_SSH" ]; then
      PORT_SSH=22
    fi


    if [[ -z "$IP" || -z "$USER_PASS" ]]; then
      log "Host $HOST com dados incompletos (sem IP ou credenciais), ignorando..." "$YELLOW"
      continue
    fi

    process_host "$HOST" "$IP" "$PORT_ZABBIX" "$USER" "$PASS" "$AVAILABLE" "$PORT_SSH"
  done
}


# Função para processar hosts a partir da resposta `trigger.get`
process_hosts_trigger_get() {
  local RESPONSE="$1"

  if ! echo "$RESPONSE" | jq -e '.result' >/dev/null; then
    log "trigger.get inválido: $RESPONSE" "$RED"
    return 1
  fi

  # Itera por cada host único de todas as triggers
  echo "$RESPONSE" \
    | jq -r '[.result[].hosts[].hostid] | unique | .[]' \
    | while read -r HOSTID; do
      # Monta e chama host.get só uma vez por host
      HOST_REQ=$(
        cat <<EOF
{"jsonrpc":"2.0","method":"host.get","params":{
  "hostids":["$HOSTID"],
  "output":["host"],
  "selectInventory":["notes"],
  "selectInterfaces":["ip","port","available"]
},"id":1}
EOF
      )
      HOST_RES=$(curl -k -s -H "Content-Type:application/json-rpc" \
        -H "Authorization: Bearer $PARAM_TOKEN" \
        -d "$HOST_REQ" https://monitor.flagee.cloud/api_jsonrpc.php)
      process_hosts_host_get "$HOST_RES"
    done
}



# Função para processar cada host
process_host() {
  local HOST="$1"
  local IP="$2"
  local PORT_ZABBIX="$3"
  local USER="$4"
  local PASS="$5"
  local AVAILABLE="$6"
  local PORT_SSH="$7"

  log "Processando HOST: $HOST (IP $IP - PORT_SSH $PORT_SSH)"
  log "Status: $PARAM_AGENT_STATUS, AVAILABLE: $AVAILABLE"

  if [ -z "$USER" ] || [ -z "$PASS" ]; then
    log "Usuario ou Senha vazios" "$RED"
    return
  fi

  check_connection "$IP" "$USER" "$PASS" "$PORT_SSH"
  CONNECTION_STATUS=$?

  case $CONNECTION_STATUS in
    0)
      log "Conexão bem-sucedida com $IP"
      zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s $HOST -k pdv.credenciais_invalidas -o 0
      DISTRO_VERSION=$(detect_distro_and_version "$IP" "$USER" "$PASS" "$PORT_SSH")
      DISTRO=$(echo "$DISTRO_VERSION" | cut -d' ' -f1)
      VERSION=$(echo "$DISTRO_VERSION" | cut -d' ' -f2)
      ARCH=$(detect_architecture "$IP" "$USER" "$PASS" "$PORT_SSH")
  
      log "Distribuição: $DISTRO, Versão: $VERSION, Arquitetura: $ARCH" "$NC"

      if [ "$PARAM_REMOVE_MONITORASAT" == 'true' ]; then
        remove_monitorasat "$USER" "$PASS" "$IP" "$DISTRO" "$VERSION" "$ARCH" "$HOST" "$PARAM_PROXY_IP" "$PORT_ZABBIX" "$PORT_SSH"
      elif [ "$PARAM_SHUTDOWN" == 'true' ]; then
        if [[ "$HOST" == *"PAGUEMENOS-LOJA032"* || "$HOST" == *"CONCENTRADOR"* ]]; then
          log "Shutdown ignorado para $HOST" "$YELLOW"
        else
          shutdown "$USER" "$PASS" "$IP" "$DISTRO" "$VERSION" "$ARCH" "$HOST" "$PORT_SSH"
        fi
      elif [ "$PARAM_BACKUP_CUPOM" == 'true' ]; then
        backup_cupom "$USER" "$PASS" "$IP" "$HOST" "$PORT_SSH"
      elif [ "$PARAM_UPDATE_ARIUSMONITOR_PARAM" == 'true' ]; then
        # Atualizar Ariusmonitor
        log "** Recriando arquivo $ARIUSMONITOR_CONFIG_FILE"
        run_sshpass "$SUDO_COMMAND bash -c 'cat << EOF > $ARIUSMONITOR_CONFIG_FILE
Server=$PARAM_PROXY_IP
ServerActive=$PARAM_PROXY_IP
ListenPort=$PORT_ZABBIX
LogFile=$ARIUSMONITOR_CONFIG_LOGFILE
PidFile=$ARIUSMONITOR_CONFIG_PIDFILE
Hostname=$HOST
BufferSize=300
AllowRoot=1
Include=$ARIUSMONITOR_CONFIG_INCLUDE
MaxLinesPerSecond=50
AllowKey=system.run[*]
UnsafeUserParameters=1
Timeout=20
EOF'" $USER $PASS $IP "" $PORT_SSH

        log "** Reiniciando o serviço do ariusmonitor-agent"
        run_sshpass "$SUDO_COMMAND /ariusmonitor/utilities/start.sh" "$USER" "$PASS" "$IP" "$PORT_SSH"

      else
        check_installation "$USER" "$PASS" "$IP" "$DISTRO" "$VERSION" "$ARCH" "$HOST" "$PARAM_PROXY_IP" "$PORT_ZABBIX" "$PORT_SSH"
      fi

      if [ "$PARAM_OUTPUT" = "json" ]; then
        # JSON cru, sem cores, sem nada mais
        printf '{"hostid": %s, "status": "%s"}\n' "$PARAM_HOSTID" "$INSTALL_STATUS"
        exit 0
      fi
      ;;
    1)
      log "Máquina não responde: $IP - PORTA $PORT_SSH" "$RED" "$LOGFILE_MACHINE_UNRESPONSIVE"
      ;;
    2)
      log "Credenciais inválidas: $IP - PORTA $PORT_SSH" "$RED" "$LOGFILE_INVALID_CREDENTIALS"
      zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -s $HOST -k pdv.credenciais_invalidas -o 1
      ;;
    3)
      log "Timeout ao conectar ao IP:  $IP - PORTA $PORT_SSH" "$YELLOW" "$LOGFILE_MACHINE_UNRESPONSIVE"
      ;;
    4)
      log "Erro desconhecido ao conectar ao IP:  $IP - PORTA $PORT_SSH" "$RED" "$LOGFILE_GENERAL"
      ;;

  esac
  log "----------------------------"
}

# Consulta hosts indisponíveis, caso --agent-status seja fornecido
if [[ $PARAM_AGENT_STATUS -ne '' ]]; then
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
    "selectInterfaces": ["ip", "port", "available"],
    "filter": {
      "available": "2"
    }
  },
  "id": 1
}
EOF
)
  log "Conectando no Zabbix-Server para filtrar hosts por agent-status"
  RESPONSE=$(curl -k -s -X POST \
  -H "Content-Type: application/json-rpc" \
  -H "Authorization: Bearer $PARAM_TOKEN" \
  -d "$JSON_REQ" 'https://monitor.flagee.cloud/api_jsonrpc.php')
  process_hosts_host_get "$RESPONSE"
else
JSON_REQ=$(cat <<-EOF
{
  "jsonrpc":"2.0",
  "method":"host.get",
  "params":{
    ${JSON_FILTER},
    "output":["host"],
    "selectInventory":["notes"],
    "selectInterfaces":["ip","port","available"]
  },
  "id":1
}
EOF
)
  log "Conectando no Zabbix-Server"
  RESPONSE=$(curl -k -s -X POST \
  -H "Content-Type: application/json-rpc" \
  -H "Authorization: Bearer $PARAM_TOKEN" \
  -d "$JSON_REQ" 'https://monitor.flagee.cloud/api_jsonrpc.php')

  # echo $JSON_REQ

  # Processar os hosts encontrados
  process_hosts_host_get "$RESPONSE"
fi

# Consulta hosts com credenciais inválidas, caso --credenciais-invalidas seja fornecido
if [[ $PARAM_CREDENCIAIS_INVALIDAS == 'true' ]]; then
  log "Iniciando Coleta de Credenciais Inválidas por grupo $PARAM_ZABBIX_GROUPID"

  JSON_REQ=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "method": "trigger.get",
  "params": {
    "output": ["description","status"],
    "filter": {
      "description": "PDV (Credenciais Inválidas)",
      "value": 1
    },
    "groupids": [$PARAM_ZABBIX_GROUPID],
    "selectHosts": ["hostid","host"],
    "expandDescription": true
  },
  "id": 2
}
EOF
)

  log "Conectando no Zabbix-Server para buscar hosts do grupo $PARAM_ZABBIX_GROUPID com a trigger alarmada"
  RESPONSE=$(curl -k -s -X POST \
      -H "Content-Type: application/json-rpc" \
      -H "Authorization: Bearer $PARAM_TOKEN" \
      -d "$JSON_REQ" 'https://monitor.flagee.cloud/api_jsonrpc.php')

  process_hosts_trigger_get "$RESPONSE"
fi