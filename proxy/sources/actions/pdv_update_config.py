# actions/pdv_update_config.py
import os
import logging
import requests
import threading
import tempfile
import hashlib
import time
from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC
# Importa o dicionário de checksums que é populado pelo pdv_asset_manager
from pdv_asset_manager import LOCAL_CHECKSUMS

def _sync_file(session: SSHSession, local_path: str, remote_path: str, needs_sudo: bool, logger, host_log_prefix):
    """
    Função auxiliar que sincroniza um único arquivo de forma idempotente,
    usando o checksum pré-calculado do dicionário global.
    """
    filename = os.path.basename(local_path)
    local_checksum = LOCAL_CHECKSUMS.get(filename)
    
    if not local_checksum:
        logger.error(f"{host_log_prefix} {RED}Checksum local para {filename} não encontrado. Envio abortado.{NC}")
        return False

    logger.info(f"{host_log_prefix} Verificando {filename} remoto em {remote_path}...")
    remote_checksum_cmd = f"sha256sum {remote_path} 2>/dev/null | cut -d' ' -f1"
    status, remote_checksum, _ = session.run(remote_checksum_cmd, use_sudo=needs_sudo)
    
    if local_checksum == remote_checksum.strip():
        logger.info(f"{host_log_prefix} {GREEN}{filename} já está atualizado. Envio ignorado.{NC}")
        return True
    
    logger.info(f"{host_log_prefix} {filename} desatualizado. Enviando nova versão...")
    try:
        session.put(local_path, remote_path, use_sudo=needs_sudo)
        status, new_remote_checksum, _ = session.run(remote_checksum_cmd, use_sudo=needs_sudo)
        if local_checksum == new_remote_checksum.strip():
            logger.info(f"{host_log_prefix} {GREEN}Envio de {filename} concluído e verificado.{NC}")
            return True
        else:
            logger.error(f"{host_log_prefix} {RED}FALHA na verificação pós-envio de {filename}.{NC}")
            return False
    except Exception as e:
        logger.error(f"{host_log_prefix} {RED}FALHA no envio de {filename}. Erro: {e}{NC}")
        return False

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Assume que os assets locais já foram baixados pelo main.py e foca em
    sincronizar os arquivos, aplicar permissões e reconfigurar o host remoto.
    """
    host_log_prefix = f"[{host['host']}]"
    logger.info(f"{host_log_prefix} INICIANDO AÇÃO 'pdv_update_config'...")
    
    needs_sudo = session.user != 'root'
    if needs_sudo:
        logger.debug(f"{host_log_prefix} Conectado como '{session.user}', usará 'sudo'.")
    else:
        logger.debug(f"{host_log_prefix} Conectado como 'root', não usará 'sudo'.")
    
    base_dir = "/ariusmonitor"
    local_dir = config.get("PARAM_LOCAL_ASSET_DIR", "/ariusmonitor/host-linux")
    remote_config_path = f"{base_dir}/conf/zabbix_agentd.conf"
    agent_process_name = f"{base_dir}/zabbix/sbin/zabbix_agentd"

    files_to_sync = {
        "geral.conf": f"{base_dir}/conf/zabbix_agentd.conf.d/geral.conf",
        "MonitoraSATc": f"{base_dir}/MonitoraSATc",
        "MonitoraSATc64": f"{base_dir}/MonitoraSATc64",
        "MonitoraSAT.sh": f"{base_dir}/MonitoraSAT.sh",
        "MonitoraImpressora": f"{base_dir}/MonitoraImpressora",
        "libs.tar.gz": f"{base_dir}/libs.tar.gz"
    }

    logger.info(f"{host_log_prefix} Etapa 1/5: Sincronizando arquivos de assets...")
    for filename, remote_path in files_to_sync.items():
        local_path = os.path.join(local_dir, filename)
        if not _sync_file(session, local_path, remote_path, needs_sudo, logger, host_log_prefix):
            logger.error(f"{host_log_prefix} {RED}Falha crítica na sincronização. Abortando update.{NC}")
            return
    logger.info(f"{host_log_prefix} {GREEN}Etapa 1/5: Sincronização de arquivos concluída.{NC}")
            
    logger.info(f"{host_log_prefix} Etapa 2/5: Aplicando permissões de execução...")
    executables_to_permission = [
        "MonitoraSATc", "MonitoraSATc64", "MonitoraSAT.sh", "MonitoraImpressora"
    ]
    all_permissions_ok = True
    for filename in executables_to_permission:
        remote_path = files_to_sync.get(filename)
        if remote_path:
            status, _, err = session.run(f"chmod +x {remote_path}", use_sudo=needs_sudo)
            if status != 0:
                logger.error(f"{host_log_prefix} {RED}Falha em {filename}: {err}{NC}")
                all_permissions_ok = False
    
    if not all_permissions_ok:
        logger.error(f"{host_log_prefix} {RED}Falha crítica nas permissões. Abortando update.{NC}")
        return
    logger.info(f"{host_log_prefix} {GREEN}Etapa 2/5: Permissões aplicadas com sucesso.{NC}")

    logger.info(f"{host_log_prefix} Etapa 3/5: Descompactando libs.tar.gz...")
    status, _, err = session.run(f"tar zxvf {base_dir}/libs.tar.gz -C {base_dir}", use_sudo=needs_sudo, logger=logger)
    if status != 0:
        logger.warning(f"{host_log_prefix} {YELLOW}Não foi possível descompactar libs.tar.gz. Erro: {err}{NC}")
    logger.info(f"{host_log_prefix} {GREEN}Etapa 3/5: Descompactação concluída.{NC}")

    logger.info(f"{host_log_prefix} Etapa 4/5: Gerando e enviando zabbix_agentd.conf...")
    proxy_ip = config.get("PARAM_PROXY_IP", "127.0.0.1")
    config_content = f"""Server={proxy_ip}
ServerActive={proxy_ip}
ListenPort={host.get('port_zabbix', 10050)}
LogFile={base_dir}/logs/zabbix_agentd.log
PidFile={base_dir}/logs/zabbix_agentd.pid
Hostname={host['host']}
BufferSize=300
AllowRoot=1
Include={base_dir}/conf/zabbix_agentd.conf.d/*
MaxLinesPerSecond=50
UnsafeUserParameters=1
Timeout=20
"""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_file:
            tmp_file.write(config_content)
            local_tmp_path = tmp_file.name
        remote_tmp_path = f"/tmp/{os.path.basename(local_tmp_path)}"
        session.put(local_tmp_path, remote_tmp_path)
        
        status, _, err = session.run(f"mv {remote_tmp_path} {remote_config_path}", use_sudo=needs_sudo, logger=logger)
        if status != 0: raise Exception(f"Falha ao mover o arquivo de configuração: {err}")
            
        logger.info(f"{host_log_prefix} {GREEN}Etapa 4/5: zabbix_agentd.conf criado com sucesso.{NC}")
    except Exception as e:
        logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 4/5. Erro: {e}{NC}")
        return
    finally:
        if 'local_tmp_path' in locals() and os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)

    # --- INÍCIO DA CORREÇÃO ---
    # Etapa 5: Reiniciar o serviço, verificar e enviar sinal.
    logger.info(f"{host_log_prefix} Etapa 5/5: Reiniciando o serviço...")
    
    # O comando de reinício é SEMPRE o start.sh.
    # O start.sh é inteligente e sabe o que fazer (systemd vs rc.d)
    restart_command = f"{base_dir}/utilities/start.sh"
    logger.debug(f"{host_log_prefix} Usando comando agnóstico: '{restart_command}'")
        
    # Executa o comando de reinício e ESPERA pela resposta
    # A variável 'needs_sudo' controla se o comando 'start.sh' será prefixado com 'sudo -S'
    status, out, err = session.run(restart_command, use_sudo=needs_sudo, logger=logger)
    if status != 0:
        logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 5/5: O script '{restart_command}' falhou.{NC} Erro: {err}")
        return
        
    logger.info(f"{host_log_prefix} Comando de reinício executado. Aguardando 3 segundos...")
    time.sleep(3) # Pausa para o serviço inicializar

    logger.info(f"{host_log_prefix} Verificando se o processo do agente está em execução...")
    status_pgrep, _, _ = session.run(f"pgrep -f '{agent_process_name}'", use_sudo=needs_sudo)

    if status_pgrep != 0:
        logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 5/5: O processo do Zabbix Agent NÃO está rodando.{NC}")
        status_log, out_log, _ = session.run(f"tail -n 10 {base_dir}/logs/zabbix_agentd.log", use_sudo=needs_sudo)
        if status_log == 0 and out_log:
            logger.debug(f"{host_log_prefix} Últimas linhas do log do agente:\n{out_log.strip()}")
        return
        
    logger.info(f"{host_log_prefix} {GREEN}Serviço reiniciado com sucesso. Processo encontrado.{NC}")
    
    logger.info(f"{host_log_prefix} Enviando sinal 'ligado' para o Zabbix...")
    sender_cmd = f"{base_dir}/zabbix/bin/zabbix_sender -c {remote_config_path} -k ligado -o 1"
    status_sender, _, _ = session.run(sender_cmd, use_sudo=needs_sudo, logger=logger)
    
    if status_sender == 0:
        logger.info(f"{host_log_prefix} {GREEN}Etapa 5/5: Sinal 'ligado' enviado com sucesso.{NC}")
    else:
        logger.warning(f"{host_log_prefix} {YELLOW}FALHA na Etapa 5/5: Sinal 'ligado' não foi enviado.{NC}")
    # --- FIM DA CORREÇÃO ---
        
    logger.info(f"{host_log_prefix} {GREEN}AÇÃO 'pdv_update_config' FINALIZADA COM SUCESSO.{NC}")