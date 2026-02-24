#!/bin/bash

set -e

echo "🔍 Verificando dependências para os scripts Python..."

# Verifica se está sendo executado como root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Este script precisa ser executado como root."
  exit 1
fi

# Atualiza os repositórios
echo "🔄 Atualizando lista de pacotes..."
apt update -y

# Array com os pacotes necessários do APT
packages=(
  python3
  python3-pip
  zabbix-sender
  jq
  curl
  ca-certificates
  sshpass
)

echo "📦 Instalando pacotes do sistema: ${packages[*]}"
apt install -y "${packages[@]}"

# Instala o mysql-connector-python com pip
echo "🐍 Instalando biblioteca Python mysql-connector-python..."
pip3 install --upgrade mysql-connector-python

echo "✅ Todas as dependências foram instaladas com sucesso."
