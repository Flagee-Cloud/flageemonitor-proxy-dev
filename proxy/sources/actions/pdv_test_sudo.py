# actions/pdv_test_sudo.py
import logging
from ssh_manager import SSHSession

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    logger.info(f"Executando teste de sudo em {host['host']}...")
    # Executamos um comando inofensivo com sudo, mas SEM fire-and-forget
    # para que possamos ver a saída de erro.
    status, stdout, stderr = session.run("whoami", use_sudo=True, logger=logger)
    
    if status == 0 and "root" in stdout:
        logger.info(f"SUCESSO: Sudo funciona em {host['host']}. Saída: {stdout.strip()}")
    else:
        logger.error(f"FALHA: Sudo não funcionou em {host['host']}. Erro: {stderr.strip()}")