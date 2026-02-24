# process_one.py

import logging
import importlib # Biblioteca para importação dinâmica
from ssh_manager import SSHSession
from utils import RED, NC
import socket
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError
from compatibility_guard import run_compatibility_precheck
from provider_adapter import resolve_effective_action_for_host, normalize_provider

def process_one(host: dict, config: dict, args, logger: logging.Logger):
    """
    Conecta-se ao host e executa a ação carregada dinamicamente.
    """
    provider = normalize_provider(host.get("provider") or getattr(args, "provider", None))
    effective_action, skip_reason = resolve_effective_action_for_host(
        resolved_action=args.action,
        canonical_action=getattr(args, "canonical_action", args.action),
        provider=provider,
        config=config,
        host=host,
        logger=logger,
    )
    if skip_reason:
        logger.info(f"[{host['host']}] {skip_reason}")
        return

    logger.info(
        f"Processando {host['host']} ({host['ip']}) para a ação '{effective_action}' "
        f"(provider={provider}, canônica={getattr(args, 'canonical_action', 'unknown')})"
    )
    
    # Tenta carregar o módulo da ação dinamicamente
    try:
        action_module = importlib.import_module(f"actions.{effective_action}")
    except ImportError:
        logger.error(
            f"{RED}Ação '{effective_action}' não encontrada. "
            f"Verifique se o arquivo 'actions/{effective_action}.py' existe.{NC}"
        )
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
        if not run_compatibility_precheck(session, host, effective_action, config, args, logger):
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
