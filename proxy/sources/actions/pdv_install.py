# actions/pdv_install.py
import os
import logging
import requests
import threading
import hashlib
from ssh_manager import SSHSession
from utils import GREEN, RED, NC
from actions.pdv_update_config import run as run_update_config

_package_downloaded = False
_download_lock = threading.Lock()
_local_package_checksum = None

def _calculate_local_checksum(file_path: str, logger: logging.Logger) -> str:
    """Calcula o checksum SHA256 de um arquivo local."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Lê o arquivo em blocos para não sobrecarregar a memória
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        checksum = sha256_hash.hexdigest()
        logger.debug(f"Checksum SHA256 local para {os.path.basename(file_path)}: {checksum}")
        return checksum
    except FileNotFoundError:
        logger.error(f"{RED}Arquivo local {file_path} não encontrado para cálculo de checksum.{NC}")
        return None

def _download_package(config: dict, logger: logging.Logger) -> bool:
    global _local_package_checksum
    repo_url = config.get("PARAM_REPO_URL", "https://ariusmonitor-repo.flagee.cloud")
    local_dir = config.get("PARAM_LOCAL_ASSET_DIR", "/ariusmonitor/host-linux")
    package_name = "ariusmonitor.tar.gz"
    url = f"{repo_url}/{package_name}"
    local_path = os.path.join(local_dir, package_name)
    
    try:
        os.makedirs(local_dir, exist_ok=True)
        logger.info(f"Baixando {url} para {local_path}...")
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        # 3. Calcula e armazena o checksum após o download
        _local_package_checksum = _calculate_local_checksum(local_path, logger)
        if not _local_package_checksum: return False

        logger.info(f"{GREEN}Pacote principal baixado com sucesso.{NC}")
        return True
    except Exception as e:
        logger.error(f"{RED}Falha ao baixar o pacote principal: {e}{NC}")
        return False

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    host_log_prefix = f"[{host['host']}]"
    global _package_downloaded, _local_package_checksum
    
    if not _package_downloaded:
        with _download_lock:
            if not _package_downloaded:
                if _download_package(config, logger):
                    _package_downloaded = True
                else:
                    return

    if not _package_downloaded:
        return

    logger.info(f"{host_log_prefix} INICIANDO AÇÃO 'pdv_install'...")

    # --- LÓGICA INTELIGENTE DE SUDO ---
    needs_sudo = session.user != 'root'
    if needs_sudo:
        logger.debug(f"{host_log_prefix} Conectado como '{session.user}', usará 'sudo'.")
    else:
        logger.debug(f"{host_log_prefix} Conectado como 'root', não usará 'sudo'.")

    local_package_path = os.path.join(config.get("PARAM_LOCAL_ASSET_DIR", "/ariusmonitor/host-linux"), "ariusmonitor.tar.gz")
    remote_tmp_path = "/tmp/ariusmonitor.tar.gz"
    
    logger.info(f"{host_log_prefix} Etapa 1/5: Verificando checksum do pacote remoto...")
    remote_checksum_cmd = f"sha256sum {remote_tmp_path} 2>/dev/null | cut -d' ' -f1"
    status, remote_checksum, _ = session.run(remote_checksum_cmd)
    remote_checksum = remote_checksum.strip()

    if _local_package_checksum == remote_checksum:
        logger.info(f"{host_log_prefix} {GREEN}Etapa 1/5: Pacote já está atualizado no host remoto. Envio ignorado.{NC}")
    else:
        logger.info(f"{host_log_prefix} Checksums diferentes. Enviando pacote...")
        try:
            session.put(local_package_path, remote_tmp_path)
            logger.info(f"{host_log_prefix} {GREEN}Etapa 1/5: Envio do pacote concluído.{NC}")
        except Exception as e:
            logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 1/5. Erro: {e}{NC}")
            return
            
    
    
    
    # --- AQUI ESTÁ A CORREÇÃO ---
    base_dir = "/ariusmonitor"
    stop_script = f"{base_dir}/utilities/stop.sh"
    setup_script = f"{base_dir}/utilities/setup.sh"
    
    # Etapa 2: Parada de serviços antigos
    logger.info(f"{host_log_prefix} Etapa 2/5: Parando serviços antigos...")
    # Garante que o script tenha permissão de execução ANTES de rodar
    session.run(f"chmod +x {stop_script}", use_sudo=needs_sudo)
    status, _, err = session.run(stop_script, use_sudo=needs_sudo, logger=logger)
    logger.info(f"{host_log_prefix} {GREEN}Etapa 2/5: Parada de serviços concluída.{NC}")
    
    # Etapa 3: Extração do pacote
    logger.info(f"{host_log_prefix} Etapa 3/5: Extraindo pacote...")
    remote_tmp_path = "/tmp/ariusmonitor.tar.gz"
    status, _, err = session.run(f"tar zxvf {remote_tmp_path} -C /", use_sudo=needs_sudo, logger=logger)
    if status != 0:
        logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 3/5: Extração. Erro: {err}{NC}")
        return
    logger.info(f"{host_log_prefix} {GREEN}Etapa 3/5: Extração concluída.{NC}")

    # Etapa 4: Execução do setup.sh remoto
    logger.info(f"{host_log_prefix} Etapa 4/5: Executando setup.sh remoto...")
    # Garante que o script recém-extraído tenha permissão de execução
    session.run(f"chmod +x {setup_script}", use_sudo=needs_sudo)
    status, _, err = session.run(setup_script, use_sudo=needs_sudo, logger=logger)
    if status != 0:
        logger.error(f"{host_log_prefix} {RED}FALHA na Etapa 4/5: setup.sh. Erro: {err}{NC}")
        return
    logger.info(f"{host_log_prefix} {GREEN}Etapa 4/5: setup.sh executado com sucesso.{NC}")
    
    # --- FIM DA CORREÇÃO ---
    
    # Etapa 5: Aplicação das configurações
    logger.info(f"{host_log_prefix} Etapa 5/5: Aplicando configurações específicas do host...")
    run_update_config(session, host, config, logger, args)
    
    logger.info(f"{host_log_prefix} {GREEN}AÇÃO 'pdv_install' FINALIZADA COM SUCESSO.{NC}")
