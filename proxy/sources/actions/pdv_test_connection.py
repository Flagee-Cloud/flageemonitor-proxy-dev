# /ariusmonitor/sources/actions/pdv_test_connection.py

from ssh_manager import SSHSession
from utils import GREEN, RED, NC
import logging

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Executa um simples comando 'echo' no host remoto para validar a conectividade
    e medir a performance da conexão SSH.
    """
    logger.info(f"Executando teste de conexão em {host['host']}...")

    # O comando a ser executado no host remoto
    command_to_run = "echo 'Teste de conexao bem-sucedido'"

    # A função session.run() já possui logs integrados de sucesso/falha
    # ao passar o logger como parâmetro.
    status, stdout, stderr = session.run(command_to_run, logger=logger)

    # Adicionamos um log final para confirmar visualmente o resultado
    if status == 0:
        logger.info(f"{GREEN}Teste em {host['host']} finalizado com sucesso.{NC}")
    else:
        # O erro detalhado já foi logado pela função session.run()
        logger.error(f"{RED}Ocorreu uma falha durante o teste em {host['host']}.{NC}")