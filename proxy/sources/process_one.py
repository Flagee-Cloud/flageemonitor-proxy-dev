# process_one.py

import logging
import importlib # Biblioteca para importação dinâmica
from ssh_manager import SSHSession
from utils import RED, NC
import socket
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError
from compatibility_guard import run_compatibility_precheck

def process_one(host: dict, config: dict, args, logger: logging.Logger):
    """
    Conecta-se ao host e executa a ação carregada dinamicamente.
    """
    logger.info(f"Processando {host['host']} ({host['ip']}) para a ação '{args.action}'")
    
    # Tenta carregar o módulo da ação dinamicamente
    try:
        action_module = importlib.import_module(f"actions.{args.action}")
    except ImportError:
        logger.error(f"{RED}Ação '{args.action}' não encontrada. Verifique se o arquivo 'actions/{args.action}.py' existe.{NC}")
        return

    session = None
    try:
        session = SSHSession(
            host=host['ip'],
            port=host['port_ssh'],
            user=host['user'],
            password=host['password'],
            timeout=config.get('ssh', {}).get('timeout', 30)
        )

        # Guardrail de compatibilidade por SO/arquitetura.
        if not run_compatibility_precheck(session, host, args.action, config, args, logger):
            logger.error(f"{RED}[{host['host']}] Ação bloqueada por incompatibilidade de ambiente.{NC}")
            return
        
        # Executa a função 'run' do módulo carregado
        action_module.run(session, host, config, logger, args)

    except NoValidConnectionsError:
        logger.error(f"{RED}Falha de conexão em {host['host']}{NC} - Host offline ou porta bloqueada.")
    except AuthenticationException:
        logger.error(f"{RED}Falha de autenticação em {host['host']}{NC} - Credenciais incorretas.")
    except (socket.timeout, TimeoutError):
        logger.error(f"{RED}Timeout ao conectar em {host['host']}{NC}.")
    except Exception as e:
        logger.error(f"{RED}Erro inesperado em {host['host']}{NC}: {type(e).__name__} - {e}")
    finally:
        if session:
            session.close()
