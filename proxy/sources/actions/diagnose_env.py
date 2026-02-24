# actions/pdv_diagnose_env.py
import logging
from ssh_manager import SSHSession
# --- INÍCIO DA CORREÇÃO ---
from utils import GREEN, YELLOW, NC
# --- FIM DA CORREÇÃO ---

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Executa comandos de diagnóstico no host remoto para verificar o ambiente,
    especialmente o PATH e a localização de comandos essenciais.
    """
    logger.info(f"--- INICIANDO DIAGNÓSTICO DE AMBIENTE EM {host['host']} ---")

    # Comando 1: Verificar o PATH
    logger.info("1. Verificando o PATH do usuário...")
    status, stdout, stderr = session.run("echo $PATH", use_sudo=False)
    if status == 0:
        logger.info(f"{GREEN}PATH:{NC} {stdout.strip()}")
    else:
        logger.error(f"Não foi possível obter o PATH. Erro: {stderr.strip()}")

    # Comando 2: Localizar 'sudo'
    logger.info("2. Localizando o comando 'sudo'...")
    status, stdout, stderr = session.run("which sudo", use_sudo=False)
    if status == 0 and stdout.strip():
        logger.info(f"{GREEN}Localização de 'sudo':{NC} {stdout.strip()}")
    else:
        # 'which' pode não estar disponível, tenta com 'type'
        status_t, stdout_t, stderr_t = session.run("type -p sudo", use_sudo=False)
        if status_t == 0 and stdout_t.strip():
             logger.info(f"{GREEN}Localização de 'sudo' (via type):{NC} {stdout_t.strip()}")
        else:
             logger.warning(f"{YELLOW}'sudo' não encontrado no PATH padrão.{NC}")

    # Comando 3: Localizar 'shutdown'
    logger.info("3. Localizando o comando 'shutdown'...")
    status, stdout, stderr = session.run("which shutdown", use_sudo=False)
    if status == 0 and stdout.strip():
        logger.info(f"{GREEN}Localização de 'shutdown':{NC} {stdout.strip()}")
    else:
        status_t, stdout_t, stderr_t = session.run("type -p shutdown", use_sudo=False)
        if status_t == 0 and stdout_t.strip():
             logger.info(f"{GREEN}Localização de 'shutdown' (via type):{NC} {stdout_t.strip()}")
        else:
             logger.warning(f"{YELLOW}'shutdown' não encontrado no PATH padrão.{NC}")
    
    logger.info(f"--- FIM DO DIAGNÓSTICO EM {host['host']} ---")