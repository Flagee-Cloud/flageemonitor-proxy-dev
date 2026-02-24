#!/usr/bin/env python3
import os
import subprocess
import sys
import argparse
from datetime import datetime
import signal
import json
import paramiko
import pexpect

# Definindo códigos de cores
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

# Variáveis globais
ARIUSMONITOR_CONFIG_FILE = "/ariusmonitor/conf/zabbix_agentd.conf"
ARIUSMONITOR_CONFIG_PIDFILE = "/ariusmonitor/logs/zabbix_agentd.pid"
ARIUSMONITOR_CONFIG_LOGFILE = "/ariusmonitor/logs/zabbix_agentd.log"
ARIUSMONITOR_CONFIG_AGENTD_PATH = "/ariusmonitor/conf/zabbix_agentd.conf.d/"
ARIUSMONITOR_CONFIG_INCLUDE = f"{ARIUSMONITOR_CONFIG_AGENTD_PATH}*"
ARIUSMONITOR_BOT_DIR = "/ariusmonitor"

# Parâmetros do script
params = {
    "pdv_ip": "",
    "loja": "",
    "pdv": "",
    "agent_status": "",
    "update_sat": False,
    "sat_associar_assinatura": False,
    "cnpj_contribuinte": "",
    "chave_assinatura": "",
    "update_ariusmonitor": False,
    "update_ariusmonitor_param": False,
    "remove_monitorasat": False,
    "ignore_config_ariusmonitor": False,
    "install_fping": False,
    "move_logs": False,
    "debbug": False,
    "unlock": False,
}

# Função para registrar LOG
def log(message, color=NC, logfile=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}{timestamp} - {message}{NC}")
    with open(logfile or "/ariusmonitor/logfile_general.log", 'a') as f:
        f.write(f"{timestamp} - {message}\n")

# Função para enviar arquivo apenas se ele existir
def safe_scp(client, local_path, remote_path):
    abs_local_path = os.path.abspath(local_path)  # Obtém o caminho absoluto
    log(f"Tentando enviar arquivo: {abs_local_path}")
    if os.path.isfile(abs_local_path):
        log(f"** Arquivo encontrado: {abs_local_path}")
        try:
            run_scp_command(client, abs_local_path, remote_path)
        except Exception as e:
            log(f"Erro ao enviar {abs_local_path}: {e}", RED)
    else:
        log(f"Arquivo não encontrado: {abs_local_path}", RED)
        log(f"Conteúdo do diretório /ariusmonitor: {os.listdir('/ariusmonitor')}", YELLOW)

# Função para carregar variáveis de ambiente do arquivo de configuração JSON
def load_env_variables(config_file_path):
    if os.path.isfile(config_file_path):
        with open(config_file_path) as f:
            config = json.load(f)
            for key, value in config.items():
                if isinstance(value, str):  # Apenas strings são válidas para variáveis de ambiente
                    os.environ[key] = value
                else:
                    log(f"Variável {key} não é uma string e não será definida como variável de ambiente", YELLOW)
            return config
    else:
        log(f"Arquivo de configuração '{config_file_path}' não encontrado!", RED)
        sys.exit(1)

# Carregar variáveis de ambiente do arquivo de configuração
config_file_path = os.path.join(ARIUSMONITOR_BOT_DIR, "config_bot.json")
config = load_env_variables(config_file_path)

# Atualizar params com os argumentos passados
params.update(vars(args))

# Define o arquivo de bloqueio
LOCKFILE = "/var/run/bot_ariusmonitor.lock"

# Verifica se o arquivo de bloqueio existe
if os.path.exists(LOCKFILE) and not params["unlock"]:
    log("Outro processo do bot_ariusmonitor está em execução.", RED)
    log(f"Para matar o processo, remova o arquivo de bloqueio {LOCKFILE} ou use 'pkill -f bot_ariusmonitor.sh'", RED)
    sys.exit(1)
else:
    # Cria o arquivo de bloqueio para indicar que este processo está em execução
    open(LOCKFILE, 'w').close()
    # Garante que o arquivo de bloqueio será removido ao sair do script, mesmo após uma interrupção
    import atexit
    atexit.register(lambda: os.remove(LOCKFILE))

log(f"LOJA: {params.get('loja', '')} - PROXY: {params.get('pdv_ip', '')}", BLUE)

# Função para capturar o sinal SIGINT (CTRL+C)
def interrupt_handler(signum, frame):
    log("Interrompendo a execução do script...", RED)
    sys.exit(1)

signal.signal(signal.SIGINT, interrupt_handler)

# Verifica o fuso horário atual
CURRENT_TIMEZONE = subprocess.getoutput("timedatectl show --property=Timezone --value")
if CURRENT_TIMEZONE != "America/Sao_Paulo":
    log("Corrigindo fuso horário para America/Sao_Paulo...", YELLOW)
    subprocess.call(["sudo", "timedatectl", "set-timezone", "America/Sao_Paulo"])
else:
    log("Fuso horário: America/Sao_Paulo.", GREEN)

# Função para verificar a conectividade com a máquina de destino
def check_connection(ip, user, password):
    try:
        subprocess.check_call(["timeout", "5", "bash", "-c", f"echo >/dev/tcp/{ip}/22"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None  # Máquina não responde

    subprocess.call(["ssh-keygen", "-R", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=user, password=password)
        return client  # Conexão bem-sucedida
    except Exception as e:
        log(f"Erro ao conectar: {e}", RED)
        return None  # Credenciais inválidas

# Função para executar um comando remoto com sudo
def run_sudo_command(client, command, sudo_password):
    shell = client.invoke_shell()
    shell.send(f"sudo -S {command}\n")
    shell.send(sudo_password + "\n")
    shell.recv(1024)  # Limpar o buffer
    while not shell.recv_ready():
        pass
    output = shell.recv(1024).decode()
    return output

# Função para transferir arquivos remotamente
def run_scp_command(client, local_path, remote_path):
    try:
        sftp = client.open_sftp()
        log(f"Tentando enviar {local_path} para {remote_path}")
        sftp.put(local_path, remote_path)
        sftp.close()
        log(f"Arquivo {local_path} enviado com sucesso para {remote_path}")
    except Exception as e:
        log(f"Erro ao transferir arquivo via SCP: {e}", RED)

# Função para executar um comando remoto
def run_ssh_command(client, command):
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    if params["debbug"]:
        log(f"Comando: {command}")
        log(f"Saída:{YELLOW} {output} {NC}")
        log(f"Erro:{RED} {error} {NC}")
    return output, error

# Função para detectar a distribuição e a versão do Linux na máquina de destino
def detect_distro_and_version(client):
    command = 'if [ -x "$(command -v lsb_release)" ]; then lsb_release -a; else cat /etc/*release; fi'
    output = run_ssh_command(client, command)
    distro, version = "unknown", "unknown"
    if "Ubuntu" in output:
        distro = "Ubuntu"
        version = next((line.split(':')[1].strip() for line in output.splitlines() if "Release" in line), "unknown")
    elif "Mint" in output:
        distro = "Mint"
        version = next((line.split(':')[1].strip() for line in output.splitlines() if "Release" in line), "unknown")
    elif "Slackware" in output:
        distro = "Slackware"
        version = next((line.split()[1] for line in output.splitlines() if "Slackware" in line), "unknown")
    return distro, version

# Função para detectar a arquitetura do sistema
def detect_architecture(client):
    command = 'uname -m'
    output = run_ssh_command(client, command)
    arch = "unknown"
    if "i386" in output or "i486" in output or "i586" in output or "i686" in output:
        arch = "i386"
    elif "x86_64" in output:
        arch = "amd64"
    return arch

# Função para atualizar configurações do Arius Monitor
def get_ariusmonitor_geral_config():
    log("Atualizando arquivo geral.conf")
    subprocess.call(["wget", "-N", "-P", ARIUSMONITOR_BOT_DIR, "https://repo.ariusmonitor.flagee.cloud/geral.conf", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Atualizando arquivo ariusmonitor.tar.gz")
    subprocess.call(["wget", "-N", "-P", ARIUSMONITOR_BOT_DIR, "https://repo.ariusmonitor.flagee.cloud/ariusmonitor.tar.gz", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Atualizando arquivo MonitoraSATc")
    subprocess.call(["wget", "-N", "-P", ARIUSMONITOR_BOT_DIR, "https://repo.ariusmonitor.flagee.cloud/MonitoraSATc", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Atualizando arquivo MonitoraSAT.sh")
    subprocess.call(["wget", "-N", "-P", ARIUSMONITOR_BOT_DIR, "https://repo.ariusmonitor.flagee.cloud/MonitoraSAT.sh", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Atualizando arquivo libs.tar.gz")
    subprocess.call(["wget", "-N", "-P", ARIUSMONITOR_BOT_DIR, "https://repo.ariusmonitor.flagee.cloud/libs.tar.gz", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if params["scripts_path"]:
        log(f"Atualizando scripts {params['scripts_path']}/scripts.tar.gz")
        subprocess.call(["wget", "-N", "-P", f"{ARIUSMONITOR_BOT_DIR}/{params['scripts_path']}", f"https://repo.ariusmonitor.flagee.cloud/{params['scripts_path']}/scripts.tar.gz", "--no-check-certificate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    log("Ajustando permissões dos arquivos MonitoraSATc e MonitoraSAT.sh")
    os.chmod(f"{ARIUSMONITOR_BOT_DIR}/MonitoraSATc", 0o777)
    os.chmod(f"{ARIUSMONITOR_BOT_DIR}/MonitoraSAT.sh", 0o777)

# Função para instalar o pacote no Ubuntu
def install_package_ariusmonitor(client, user, password, ip, distro, version, arch, host, ip_proxy, port):
    log('Iniciando função install_package_ariusmonitor', YELLOW)
    package_file = "ariusmonitor.tar.gz"
    package_path = "/ariusmonitor/ariusmonitor.tar.gz"

    # Verifica se o arquivo do pacote existe
    if not os.path.exists(package_path):
        log(f"** Pacote não encontrado {package_path}")
        return

    if params["move_logs"]:
        log("** Movendo logs antigos do Arius PDV para a pasta /posnet/logs_old/")
        run_sudo_command(client, "mkdir /posnet/logs_old/", password)
        run_sudo_command(client, "find /posnet -maxdepth 1 -name 'log*.txt' -type f -mtime +1 -exec mv {} /posnet/logs_old/ \\;", password)
        run_sudo_command(client, "find /posnet -maxdepth 1 -name 'nfiscal*.txt' -type f -mtime +1 -exec mv {} /posnet/logs_old/ \\;", password)

    base_destino = "~"

    # Inicia o envio do pacote
    log(f"** Enviando pacote {package_file} para {ip}", NC, "/ariusmonitor/logfile_htconfig_notinstalled.log")
    run_scp_command(client, package_path, f"{base_destino}/{package_file}")
    run_sudo_command(client, f"rm -f /ariusmonitor.tar.gz >/dev/null 2>&1", password)
    run_sudo_command(client, f"mv {base_destino}/{package_file} /", password)

    log(f"** Descompactando {package_file} no {distro} {version}")
    run_sudo_command(client, f"tar zxvf /{package_file} -C /", password)

    log(f"** Parando serviço {package_file} no {distro} {version}")
    run_sudo_command(client, f"/ariusmonitor/utilities/stop.sh", password)

    log(f"** Instalando pacote ariusmonitor no {distro} {version}")
    run_sudo_command(client, f"/ariusmonitor/utilities/setup.sh", password)

    log("** ariusmonitor instalado com sucesso", GREEN)
    
    # Atualiza as configurações do ariusmonitor-agent
    log("** Atualizando configurações do ariusmonitor-agent")
    update_ariusmonitor_agent_config(client, user, password, ip, ip_proxy, host, distro, version, port)

# Função para atualizar a configuração do 'ariusmonitor-agent'
def update_ariusmonitor_agent_config(client, user, password, ip, ip_proxy, host, distro, version, port):
    log('Iniciando função update_ariusmonitor_agent_config', '\033[0;33m')
    base_destino = "~"

    # Verificando e enviando arquivo MonitoraSATc
    safe_scp(client, "/ariusmonitor/MonitoraSATc", f"{base_destino}/MonitoraSATc")
    run_sudo_command(client, f"mv {base_destino}/MonitoraSATc /ariusmonitor", password)

    # Criando arquivo de error log do MonitoraSATc
    log(f"** Criando arquivo /ariusmonitor/monitora_error.log")
    run_sudo_command(client, f"touch /ariusmonitor/monitora_error.log && chmod 777 /ariusmonitor/monitora_error.log", password)

    # Verificando e enviando arquivo MonitoraSAT.sh
    safe_scp(client, "/ariusmonitor/MonitoraSAT.sh", f"{base_destino}/MonitoraSAT.sh")
    run_sudo_command(client, f"mv {base_destino}/MonitoraSAT.sh /ariusmonitor", password)

    # Verificando e enviando arquivo libs.tar.gz
    safe_scp(client, "/ariusmonitor/libs.tar.gz", f"{base_destino}/libs.tar.gz")
    run_sudo_command(client, f"mv {base_destino}/libs.tar.gz /ariusmonitor", password)

    log("** Descompactando /ariusmonitor/libs.tar.gz")
    run_sudo_command(client, f"tar zxvf /ariusmonitor/libs.tar.gz -C /ariusmonitor", password)

    # Verificando e enviando arquivo geral.conf
    safe_scp(client, "/ariusmonitor/geral.conf", f"{base_destino}/geral.conf")
    run_sudo_command(client, f"mv {base_destino}/geral.conf /ariusmonitor/conf/zabbix_agentd.conf.d", password)

    log("** Executando /ariusmonitor/utilities/update.sh")
    run_sudo_command(client, f"/ariusmonitor/utilities/update.sh", password)

    log(f"** Recriando arquivo /ariusmonitor/conf/zabbix_agentd.conf")
    config_content = f"""
Server={ip_proxy}
ServerActive={ip_proxy}
ListenPort={port}
LogFile=/ariusmonitor/logs/zabbix_agentd.log
PidFile=/ariusmonitor/logs/zabbix_agentd.pid
Hostname={host}
BufferSize=300
AllowRoot=1
Include=/ariusmonitor/conf/zabbix_agentd.conf.d/*
MaxLinesPerSecond=100
AllowKey=system.run[*]
UnsafeUserParameters=1
Timeout=20
"""
    run_sudo_command(client, f"echo '{config_content}' | tee /ariusmonitor/conf/zabbix_agentd.conf > /dev/null", password)

    if distro in ["Ubuntu", "Mint"]:
        log("** Configurando SUDOER para executar MonitoraSAT")
        sudoers_content = f"""
ariusmonitor ALL = NOPASSWD: /ariusmonitor/MonitoraSATc
ariusmonitor ALL = NOPASSWD: /ariusmonitor/MonitoraSAT.sh
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill MonitoraSATc
ariusmonitor ALL = NOPASSWD: /bin/bash -c /ariusmonitor/MonitoraSATc
ariusmonitor ALL = NOPASSWD: /usr/bin/pkill -f "MonitoraSATc"
ariusmonitor ALL = NOPASSWD: /usr/bin/pgrep -x "MonitoraSATc"
"""
        run_sudo_command(client, f"echo '{sudoers_content}' | tee /etc/sudoers.d/ariusmonitor > /dev/null", password)

    if params["sat_associar_assinatura"] and (params["loja"] or params["pdv_ip"]):
        if not params["cnpj_contribuinte"] or not params["chave_assinatura"]:
            log("** Para associar uma assinatura ao SAT, informe os valores dos parâmetros --cnpj-contribuinte e --chave-assinatura", '\033[0;31m', "/ariusmonitor/logfile_monitorasat.log")
        else:
            log(f"** Iniciando Associação de Assinatura do SAT no PDV {host}", '\033[0;32m', "/ariusmonitor/logfile_monitorasat.log")
            run_sudo_command(client, f"/ariusmonitor/MonitoraSATc --func AssociarAssinatura --cnpj-contribuinte {params['cnpj_contribuinte']} --chave \"{params['chave_assinatura']}\"", password)
    elif params["sat_associar_assinatura"] and not (params["loja"] or params["pdv_ip"]):
        log("** Para associar uma assinatura ao SAT, informe um valor para --loja ou --pdv-ip", '\033[0;31m', "/ariusmonitor/logfile_monitorasat.log")

    if params["update_sat"]:
        log(f"** Iniciando Atualização do SAT no PDV {host}", '\033[0;32m', "/ariusmonitor/logfile_monitorasat.log")
        run_sudo_command(client, f"/ariusmonitor/MonitoraSATc --func AtualizarSoftwareSAT", password)

    log("** Reiniciando o serviço do ariusmonitor-agent")
    run_sudo_command(client, f"/ariusmonitor/utilities/start.sh", password)

    log("** Enviando trapper ligado=1")
    run_sudo_command(client, f"/ariusmonitor/zabbix/bin/zabbix_sender -c /ariusmonitor/conf/zabbix_agentd.conf -k ligado -o 1", password)

# Função para instalar o pacote no Ubuntu
def remove_monitorasat(client, user, password, ip, distro, version, arch, host, ip_proxy, port):
    log('Iniciando função remove_monitorasat', YELLOW)

    log(f"** Removendo MonitoraSAT para {ip}", NC, "/ariusmonitor/logfile_htconfig_notinstalled.log")
    run_sudo_command(client, f"rm -f /ariusmonitor/MonitoraSATc", password)
    run_sudo_command(client, f"rm -f /ariusmonitor/MonitoraSAT", password)
    run_sudo_command(client, f"rm -f /ariusmonitor/MonitoraSAT.sh", password)

# Função para verificar a instalação do monitoramento
def check_installation(client, user, password, ip, distro, version, arch, host, ip_proxy, port):
    log('Iniciando função check_installation', YELLOW)

    ariusmonitor_agent_installed = run_ssh_command(client, f"ls /ariusmonitor/conf/zabbix_agentd.conf 2>/dev/null")[0]
    
    if not ariusmonitor_agent_installed or params["update_ariusmonitor"]:
        log("** Instalando novo ariusmonitor-agent", GREEN)
        install_package_ariusmonitor(client, user, password, ip, distro, version, arch, host, ip_proxy, port)
    else:
        if not params["ignore_config_ariusmonitor"]:
            log("** ariusmonitor-agent encontrado", BLUE)
            log("** Atualizando configurações do ariusmonitor-agent")
            update_ariusmonitor_agent_config(client, user, password, ip, ip_proxy, host, distro, version, port)
        else:
            log("** ariusmonitor-agent encontrado", BLUE)
            log("** Ignorando atualização do ariusmonitor")

# Certifique-se de que PARAM_TOKEN está sendo lido corretamente
PARAM_TOKEN = config.get("PARAM_TOKEN")
if not PARAM_TOKEN:
    log("Token de autenticação não encontrado. Verifique o arquivo de configuração.", RED)
    sys.exit(1)

# Certifique-se de que PARAM_REDE está sendo lido corretamente
PARAM_REDE = config.get("PARAM_REDE")
if not PARAM_REDE:
    log("Rede não encontrada. Verifique o arquivo de configuração.", RED)
    sys.exit(1)

# Certifique-se de que PARAM_PROXY_IP está sendo lido corretamente
PARAM_PROXY_IP = config.get("PARAM_PROXY_IP")
if not PARAM_PROXY_IP:
    log("Proxy IP não encontrado. Verifique o arquivo de configuração.", RED)
    sys.exit(1)

# Defina um valor padrão para PARAM_PORT se não estiver presente
PARAM_PORT = config.get("PARAM_PORT", "10051")

# Inicializar variáveis para filtro
filtro_host = ""
filtro_host_ip = ""

# Verifica e constrói o filtro com base nos parâmetros fornecidos
if params["loja"] and params["pdv"]:
    filtro_host = f"{params['loja']}-{params['pdv']}"
elif params["loja"]:
    filtro_host = params["loja"]
elif params["pdv_ip"]:
    filtro_host_ip = f",\"filter\": {{\"ip\": \"{params['pdv_ip']}\"}}"

log(f"###### Iniciando Bot Arius Monitor para {PARAM_REDE} {params['loja']} {params['pdv']} {params['pdv_ip']}", GREEN)

# Verifique e construa o filtro com base nos parâmetros fornecidos
json_req = f"""
{{
  "jsonrpc": "2.0",
  "method": "host.get",
  "params": {{
    "search": {{
      "host": ["{PARAM_REDE}-{filtro_host}"]
    }},
    "output": ["host"],
    "selectInventory": ["notes"],
    "selectInterfaces": ["ip", "port", "available"]
    {filtro_host_ip}
  }},
  "auth": "{PARAM_TOKEN}",
  "id": 1
}}
"""

log(f"JSON de solicitação: {json_req}", YELLOW)
log("Conectando no Zabbix-Server")
response = subprocess.getoutput(f"curl -k -s -X POST -H 'Content-Type: application/json-rpc' -d '{json_req}' 'https://monitor.flagee.cloud/api_jsonrpc.php'")
log(f"Resposta da API do Zabbix: {response}", YELLOW)

try:
    response_json = json.loads(response)
    if "result" not in response_json:
        log(f"Erro na resposta da API do Zabbix: {response_json}", RED)
        sys.exit(1)
except json.JSONDecodeError as e:
    log(f"Erro ao decodificar JSON: {e}", RED)
    sys.exit(1)

# Loop principal para processar os IPs e credenciais de acesso
for line in response_json["result"]:
    available = line["interfaces"][0]["available"]

    if params["agent_status"]:
        if available != params["agent_status"]:
            continue
    
    host = line["host"]
    ip = line["interfaces"][0]["ip"]
    port = line["interfaces"][0]["port"]

    # Verificar se "inventory" existe e não está vazio
    if "inventory" in line and line["inventory"]:
        user_pass = line["inventory"]["notes"]
        user, password = user_pass.split(',')
    else:
        log(f"Inventory vazio para o host {host}. Pulando...", RED)
        continue

    log(f"Processando HOST: {host} (IP {ip})")
    log(f"Status: {params['agent_status']}, AVAILABLE: {available}")

    if not user or not password:
        log("Usuario ou Senha vazios", RED)
        continue 

    client = check_connection(ip, user, password)

    if client:
        subprocess.call(["zabbix_sender", "-c", "/etc/zabbix/zabbix_agentd.conf", "-s", host, "-k", "pdv.credenciais_invalidas", "-o", "0"])

        distro, version = detect_distro_and_version(client)
        arch = detect_architecture(client)
        log(f"Conexão bem-sucedida com {ip}")
        log(f"Distribuição: {distro}, Versão: {version}, Arquitetura: {arch}", NC)
        
        if params["remove_monitorasat"]:
            remove_monitorasat(client, user, password, ip, distro, version, arch, host, PARAM_PROXY_IP, PARAM_PORT)
        else:
            check_installation(client, user, password, ip, distro, version, arch, host, PARAM_PROXY_IP, PARAM_PORT)
        
        client.close()
    else:
        log(f"Máquina não responde ou credenciais inválidas: {ip}", RED, "/ariusmonitor/logfile_invalid_credentials.log")
        subprocess.call(["zabbix_sender", "-c", "/etc/zabbix/zabbix_agentd.conf", "-s", host, "-k", "pdv.credenciais_invalidas", "-o", "1"])

    log("------------------------------------")

def update_proxy_config():
    log('Iniciando função update_proxy_config', YELLOW)
    log("** Atualizando Configurações do Proxy antes de atualizar os PDVs", BLUE)
    subprocess.call(["sudo", "zabbix_proxy", "-R", "config_cache_reload"])
    subprocess.call(["sudo", "zabbix_proxy", "-R", "housekeeper_execute"])

update_proxy_config()
get_ariusmonitor_geral_config()


def main():
    # Parser de argumentos
    parser = argparse.ArgumentParser(description="Bot AriusMonitor em Python")
    parser.add_argument('--pdv-ip', dest='pdv_ip')
    parser.add_argument('--loja', dest='loja')
    parser.add_argument('--pdv', dest='pdv')
    parser.add_argument('--agent-status', dest='agent_status')
    parser.add_argument('--cnpj-contribuinte', dest='cnpj_contribuinte')
    parser.add_argument('--chave-assinatura', dest='chave_assinatura')
    parser.add_argument('--update-ariusmonitor', action='store_true')
    parser.add_argument('--update-ariusmonitor-param', action='store_true')
    parser.add_argument('--update-sat', action='store_true')
    parser.add_argument('--remove-monitorasat', action='store_true')
    parser.add_argument('--force-monitorasat', action='store_true')
    parser.add_argument('--sat-associar-assinatura', action='store_true')
    parser.add_argument('--ignore-config-ariusmonitor', action='store_true')
    parser.add_argument('--install-fping', action='store_true')
    parser.add_argument('--move-logs', action='store_true')
    parser.add_argument('--debbug', action='store_true')
    parser.add_argument('--unlock', action='store_true')
    parser.add_argument('--output', choices=['json','text'], default='text')

    args = parser.parse_args()
    QUIET_JSON = (args.output == 'json')

    # Carregar variáveis de ambiente
    load_env_variables(os.path.join(ARIUSMONITOR_BOT_DIR, "config_bot.json"))

    # Lockfile
    if os.path.exists(LOCKFILE) and not args.unlock:
        log("Outro processo em execução.", RED)
        sys.exit(1)
    open(LOCKFILE, 'w').close()
    import atexit; atexit.register(lambda: os.remove(LOCKFILE))

    # Ajuste de fuso
    tz = subprocess.getoutput("timedatectl show --property=Timezone --value")
    if tz != "America/Sao_Paulo":
        log("Corrigindo timezone…", YELLOW)
        subprocess.call(["sudo","timedatectl","set-timezone","America/Sao_Paulo"])

    update_proxy_config()
    get_ariusmonitor_geral_config()

    # Requisição Zabbix
    filtro = build_json_filter(args, PARAM_REDE)
    json_req = build_zabbix_request(filtro, PARAM_TOKEN)
    if not QUIET_JSON: log(f"JSONReq: {json_req}", YELLOW)
    resp = subprocess.getoutput(
        f"curl -k -s -X POST -H 'Content-Type:application/json' -d '{json_req}' https://monitor.flagee.cloud/api_jsonrpc.php"
    )
    if not QUIET_JSON: log(f"Resposta: {resp}", YELLOW)
    data = json.loads(resp)

    final = {"hosts": []}
    for entry in data.get("result", []):
        host = entry['host']
        ip = entry['interfaces'][0]['ip']
        port = entry['interfaces'][0]['port']
        notes = entry['inventory']['notes'] if entry.get('inventory') else ''
        user, password = notes.split(',') if ',' in notes else (None, None)

        host_rec = {"host": host, "ip": ip, "steps": []}

        # 1) check_connection
        ok, msg = check_connection(ip, user, password)
        host_rec['steps'].append({"name":"check_connection","status":'ok' if ok else 'error',"message": msg or ''})
        if not ok:
            final['hosts'].append(host_rec)
            continue

        # 2) detect_distro_and_version
        distro, ver = detect_distro_and_version(ok)
        host_rec['steps'].append({"name":"detect_distro_and_version","status":"ok","message": f"{distro} {ver}"})

        # 3) install or update
        if args.remove_monitorasat:
            ok,msg = remove_monitorasat(ok)
            step_name = 'remove_monitorasat'
        else:
            ok,msg = check_installation(ok)
            step_name = 'install_or_update'
        host_rec['steps'].append({"name": step_name, "status": 'ok' if ok else 'error', "message": msg or ''})

        final['hosts'].append(host_rec)

    if args.output == 'json':
        print(json.dumps(final, ensure_ascii=False, indent=2))
        sys.exit(0)

# Ponto de entrada
if __name__ == '__main__':
    main()
