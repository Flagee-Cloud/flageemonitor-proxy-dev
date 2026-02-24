#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Configurações de cores ANSI
VERDE='\033[0;32m'
AMARELO='\033[1;33m'
VERMELHO='\033[0;31m'
NEUTRO='\033[0m'

# -----------------------------------------------------------------------------
# Variáveis de diretório e binários
REPO_DIR="/ariusmonitor/.cache/arius_repo"
DEST_DIR="/ariusmonitor"
PYTHON_COMPAT="3.12"
PYTHON_BIN="/usr/bin/python${PYTHON_COMPAT}"
VENV_DIR="${DEST_DIR}/venv"
REPO_URL="${FLAGEEMONITOR_DEPLOY_REPO_URL:-git@github.com:Flagee-Cloud/flageemonitor-proxy-deploy.git}"
REPO_BRANCH="${FLAGEEMONITOR_DEPLOY_REPO_BRANCH:-main}"

# -----------------------------------------------------------------------------
# Função de log colorido
log() {
  local color="$1"; shift
  printf "%b%s%b\n" "${color}" "$*" "${NEUTRO}"
}

# -----------------------------------------------------------------------------
log "${AMARELO}" "Atualizando runtime/, scripts/, host-linux/, postgresql/ e certi_api.pem..."

# Clonagem seletiva (cache local para evitar baixar tudo toda vez)
mkdir -p "${REPO_DIR}"
cd "${REPO_DIR}"

# -----------------------------------------------------------------------------
log "${AMARELO}" "Instalando pacotes de sistema necessários..."

# --- INÍCIO DA CORREÇÃO ---
log "${AMARELO}" "Adicionando repositório PPA 'deadsnakes' para obter o Python 3.12..."
# Garante que o comando add-apt-repository esteja disponível
apt install -y software-properties-common
# Adiciona o PPA de forma não interativa
add-apt-repository -y ppa:deadsnakes/ppa
# Atualiza a lista de pacotes NOVAMENTE para incluir os pacotes do PPA
apt update
# --- FIM DA CORREÇÃO ---

# Agora a instalação do Python 3.12 irá funcionar
apt install -y git "python${PYTHON_COMPAT}" "python${PYTHON_COMPAT}-venv"

# -----------------------------------------------------------------------------

if [[ ! -d ".git" ]]; then
  git init -q
  git remote add origin "${REPO_URL}"
fi

git config core.sparseCheckout true
git sparse-checkout init --cone
git sparse-checkout set runtime scripts host-linux postgresql certi_api.pem

git fetch --depth=1 origin "${REPO_BRANCH}"
git checkout -B "${REPO_BRANCH}" "origin/${REPO_BRANCH}"
git reset --hard "origin/${REPO_BRANCH}"
log "${AMARELO}" "HEAD atualizado para $(git rev-parse --short HEAD)"

# Copia para o destino (força atualização e remove arquivos antigos)
mkdir -p "${DEST_DIR}"
rm -rf "${DEST_DIR}/runtime" "${DEST_DIR}/scripts" "${DEST_DIR}/host-linux" "${DEST_DIR}/postgresql"
rm -f "${DEST_DIR}/certi_api.pem"
cp -a runtime scripts host-linux postgresql "${DEST_DIR}/"
cp -f certi_api.pem "${DEST_DIR}/certi_api.pem"

# Ajusta permissões
find "${DEST_DIR}" -type f -name "*.sh" -exec chmod +x {} \;
log "${VERDE}" "Pastas e certificado atualizados com sucesso em ${DEST_DIR}"

log "${AMARELO}" "Criando ambiente virtual Python em ${VENV_DIR}..."
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

# Ativa venv ou sai em erro
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
else
  log "${VERMELHO}" "Erro: não encontrei ${VENV_DIR}/bin/activate"
  exit 1
fi

# -----------------------------------------------------------------------------
log "${AMARELO}" "Atualizando pip e instalando dependências Python..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install mysql-connector-python paramiko pexpect requests scapy psutil

deactivate

# -----------------------------------------------------------------------------
log "${AMARELO}" "Configurando alias 'ariusrun'..."
# remove antigas e adiciona nova
sed -i '/alias ariusrun=/d' /root/.bashrc
printf "alias ariusrun='%s/bin/python'\n" "${VENV_DIR}" >> /root/.bashrc
alias ariusrun="${VENV_DIR}/bin/python"

log "${VERDE}" "Alias 'ariusrun' configurado. Use: ariusrun /ariusmonitor/runtime/SeuScript.py"


# ----------------------------------------------------------------------------- 

log "${AMARELO}" "Verificando se o repositório universe está habilitado..."
if ! grep -Rq "^deb .*universe" /etc/apt/sources.list /etc/apt/sources.list.d; then
  log "${AMARELO}" "Repositório universe não encontrado. Habilitando..."
  add-apt-repository -y universe
  apt update
else
  log "${VERDE}" "Repositório universe já está habilitado."
fi

log "${AMARELO}" "Instalando conntrack (modo não interativo)..."
DEBIAN_FRONTEND=noninteractive apt install -y conntrack

log "${AMARELO}" "Atualizando arquivo geral.conf"
if wget -q -N -P "/ariusmonitor/" "https://ariusmonitor-repo.flagee.cloud/geral.conf" --no-check-certificate; then
  log "${VERDE}" "Arquivo geral.conf baixado com sucesso."
else
  log "${VERMELHO}" "Erro ao baixar geral.conf. Abortando."
  exit 1
fi

log "${AMARELO}" "Copiando para /etc/zabbix/zabbix_agentd.d e /etc/zabbix/zabbix_agent2.d"
cp -u /ariusmonitor/geral.conf /etc/zabbix/zabbix_agentd.d/ 2>/dev/null || log "${AMARELO}" "Diretório zabbix_agentd.d não encontrado"
cp -u /ariusmonitor/geral.conf /etc/zabbix/zabbix_agent2.d/ 2>/dev/null || log "${AMARELO}" "Diretório zabbix_agent2.d não encontrado"

log "${AMARELO}" "Ajustando permissões em /etc/sudoers.d/zabbix_conntrack"
echo "zabbix ALL=(root) NOPASSWD: /usr/sbin/conntrack" > /etc/sudoers.d/zabbix_conntrack
chmod 440 /etc/sudoers.d/zabbix_conntrack

log "${AMARELO}" "Ajustando permissões em /ariusmonitor/scripts"
chmod -R 777 /ariusmonitor/scripts

log "${AMARELO}" "Reiniciando serviço zabbix-agent e/ou zabbix-agent2"
systemctl restart zabbix-agent 2>/dev/null || log "${AMARELO}" "zabbix-agent não está ativo"
systemctl restart zabbix-agent2 2>/dev/null || log "${AMARELO}" "zabbix-agent2 não está ativo"

log "${AMARELO}" "Ajustando timeout de nf_conntrack tcp e udp"
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=120
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30 # Corrigido para aplicar com sysctl
sysctl -w net.netfilter.nf_conntrack_udp_timeout=30       # Corrigido para aplicar com sysctl

log "${VERDE}" "Fim do gitclone.sh"
