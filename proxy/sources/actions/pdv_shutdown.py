# actions/pdv_shutdown.py

from datetime import datetime
from ssh_manager import SSHSession
from utils import YELLOW, NC
import logging

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Desliga o host remotamente, adaptando-se para usar sudo ou não,
    dependendo do usuário da conexão.
    """
    logger.info(f"Executando ação 'shutdown' em {host['host']}...")

    host_ip = host.get("ip")

    # 1. Ignora concentradores para evitar desligamento indevido
    concentradores = set(config.get("PARAM_IP_CONCENTRADORES", []) or [])
    for item in config.get("CONCENTRADORES", []) or []:
        ip = item.get("ip") if isinstance(item, dict) else None
        if ip:
            concentradores.add(ip)
    if host_ip in concentradores:
        logger.info(f"{YELLOW}Host {host['host']} ({host_ip}) é concentrador e será ignorado.{NC}")
        return

    # 2. Verifica a lista de exceção
    exception_ips = config.get("shutdown_exception_ips", [])
    if host_ip in exception_ips:
        logger.info(f"{YELLOW}Host {host['host']} ({host_ip}) está na lista de exceção e será ignorado.{NC}")
        return

    # 3. Verifica a janela de horário
    shutdown_config = config.get("shutdown_window", {})
    start_hour = shutdown_config.get("start", 22)
    end_hour = shutdown_config.get("end", 6)
    hora_atual = datetime.now().hour
    is_time_to_shutdown = (start_hour > end_hour) and (hora_atual >= start_hour or hora_atual <= end_hour)

    if not is_time_to_shutdown:
        logger.warning(f"{YELLOW}Ação de desligamento ignorada. Fora do horário permitido.{NC}")
        return

    logger.info(f"Horário permitido. Enviando comando de desligamento...")

    # Define o comando base
    shutdown_command = "/sbin/shutdown -h now"
    needs_sudo = True
    
    # Se o usuário da sessão já for 'root', não precisamos usar 'sudo'.
    # Isso funcionará para os Slackwares assim que as credenciais no Zabbix forem atualizadas para 'root'.
    if session.user == 'root':
        needs_sudo = False
        logger.info("Conectado como 'root', executando comando diretamente.")
    else:
        # Para os Ubuntus, nosso teste provou que o sudo funciona.
        logger.info(f"Conectado como '{session.user}', usando 'sudo' para elevação.")

    # A função run do ssh_manager já sabe como lidar com o sudo.
    # Usamos fire_and_forget para garantir que o comando seja entregue.
    session.run(
        shutdown_command,
        use_sudo=needs_sudo,
        logger=logger,
        fire_and_forget=True
    )
    
    logger.info(f"Comando de desligamento para {host['host']} enviado com sucesso.")
