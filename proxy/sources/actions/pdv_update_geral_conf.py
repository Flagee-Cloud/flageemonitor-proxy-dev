# /ariusmonitor/sources/actions/pdv_update_geral_conf.py

import os
import logging
import requests
import threading
from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC

# --- Variáveis de Controle ---
# Usadas para garantir que o download aconteça apenas uma vez, de forma segura entre as threads.
_is_file_updated = False
_download_lock = threading.Lock()

def _download_latest_config(local_path: str, logger: logging.Logger) -> bool:
    """
    Baixa o arquivo de configuração da URL e o salva localmente.
    Retorna True em caso de sucesso, False em caso de falha.
    """
    url = "https://ariusmonitor-repo.flagee.cloud/geral.conf"
    
    try:
        logger.info(f"Baixando arquivo de: {url}")
        
        # Garante que o diretório local exista
        local_dir = os.path.dirname(local_path)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
            logger.info(f"Diretorio local '{local_dir}' criado.")

        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Lança um erro se a requisição falhar (ex: 404, 500)

        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"{GREEN}Arquivo baixado e salvo com sucesso em '{local_path}'.{NC}")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"{RED}Falha ao baixar o arquivo de configuração: {e}{NC}")
        return False
    except IOError as e:
        logger.error(f"{RED}Falha ao salvar o arquivo de configuração em '{local_path}': {e}{NC}")
        return False


def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Baixa a versão mais recente do geral.conf (apenas uma vez), envia para o host
    remoto e reinicia o serviço ariusmonitor.
    """
    global _is_file_updated

    # --- Etapa 1: Download do arquivo (controlado por lock) ---
    if not _is_file_updated:
        with _download_lock:
            # Double-checked locking: verifica novamente após adquirir o lock
            if not _is_file_updated:
                local_geral_path = config.get('PARAM_PATH_GERAL_LOCAL', '/ariusmonitor/host-linux/geral.conf')
                success = _download_latest_config(local_geral_path, logger)
                if success:
                    _is_file_updated = True
                else:
                    logger.error(f"{RED}Download inicial do geral.conf falhou. Ação será abortada para todos os hosts.{NC}")
                    # A flag continua False, fazendo com que todas as outras threads parem.

    # Se a flag global não for True, significa que o download falhou. Aborta a execução.
    if not _is_file_updated:
        logger.warning(f"Execução em {host['host']} cancelada devido à falha no download do arquivo de configuração.")
        return

    logger.info(f"Executando ação 'update_geral_conf' em {host['host']}...")
    local_geral = config.get('PARAM_PATH_GERAL_LOCAL')
    remote_geral = config.get('PARAM_PATH_GERAL_REMOTE', '/ariusmonitor/conf/zabbix_agentd.conf.d/geral.conf')
    base_dir = config.get('PARAM_BASE_DIR', '/ariusmonitor')
    restart_script = os.path.join(base_dir, "utilities", "start.sh")

    # --- Etapa 2: Envio do arquivo para o host remoto ---
    try:
        logger.info(f"Enviando '{local_geral}' para '{remote_geral}'...")
        session.put(local_geral, remote_geral, use_sudo=True)
        logger.info(f"{GREEN}Arquivo enviado com sucesso para {host['host']}.{NC}")
    except Exception as e:
        logger.error(f"{RED}Falha ao enviar o arquivo para {host['host']}: {e}{NC}")
        return

    # --- Etapa 3: Reinício do serviço no host remoto ---
    logger.info(f"Reiniciando o serviço ariusmonitor em {host['host']}...")
    session.run(restart_script, use_sudo=True, logger=logger, fire_and_forget=True)