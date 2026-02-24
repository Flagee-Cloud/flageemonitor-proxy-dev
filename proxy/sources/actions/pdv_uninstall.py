# actions/pdv_uninstall.py
import logging
from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC

def _run_command(session: SSHSession, cmd: str, needs_sudo: bool, logger, host_log_prefix, ignore_errors=False):
    """Função auxiliar para executar um comando e logar o resultado."""
    status, _, err = session.run(cmd, use_sudo=needs_sudo, logger=logger)
    if status != 0 and not ignore_errors:
        logger.error(f"{host_log_prefix} {RED}Falha ao executar '{cmd}'. Erro: {err}{NC}")
        return False
    elif status != 0 and ignore_errors:
        logger.warning(f"{host_log_prefix} {YELLOW}Comando '{cmd}' falhou, mas o erro foi ignorado.{NC}")
        return True # Retorna sucesso mesmo com erro
    return True

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Desinstala completamente o AriusMonitor e seus componentes do host remoto.
    """
    host_log_prefix = f"[{host['host']}]"
    logger.info(f"{host_log_prefix} INICIANDO AÇÃO 'pdv_uninstall'...")

    needs_sudo = session.user != 'root'
    base_dir = "/ariusmonitor"

    # --- Etapa 1: Detectar Sistema de Inicialização ---
    logger.info(f"{host_log_prefix} Etapa 1/6: Detectando sistema de inicialização...")
    # Verifica a existência do systemctl para determinar o sistema
    status, _, _ = session.run("which systemctl", use_sudo=needs_sudo)
    is_systemd = status == 0
    if is_systemd:
        logger.info(f"{host_log_prefix} Sistema usa systemd.")
    else:
        logger.info(f"{host_log_prefix} Sistema usa SysVinit/rc.d (ou não identificado).")

    # --- Etapa 2: Parar e Desabilitar Serviços ---
    logger.info(f"{host_log_prefix} Etapa 2/6: Parando e desabilitando serviços...")
    if is_systemd:
        # Tenta parar e desabilitar os serviços systemd. Ignora erros caso não existam.
        _run_command(session, "systemctl stop ariusmonitor.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "systemctl disable ariusmonitor.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "systemctl stop ariusmonitor-shutdown.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "systemctl disable ariusmonitor-shutdown.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "systemctl stop pdvstate.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "systemctl disable pdvstate.service", needs_sudo, logger, host_log_prefix, ignore_errors=True)
    else:
        # Tenta parar e desabilitar serviços SysVinit/rc.d
        _run_command(session, "/etc/init.d/ariusmonitor stop", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "update-rc.d -f ariusmonitor remove", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "/etc/init.d/pdvstate stop", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        _run_command(session, "update-rc.d -f pdvstate remove", needs_sudo, logger, host_log_prefix, ignore_errors=True)
        # Slackware specific rc.d stop (already covered partially by rc.0/rc.6 cleanup later)
        _run_command(session, "/etc/rc.d/rc.ariusmonitor stop", needs_sudo, logger, host_log_prefix, ignore_errors=True)

    # Garante que qualquer processo remanescente seja encerrado
    _run_command(session, "pkill -f /ariusmonitor/zabbix/sbin/zabbix_agentd", needs_sudo, logger, host_log_prefix, ignore_errors=True)
    _run_command(session, "pkill -f /ariusmonitor/utilities/pdvstate", needs_sudo, logger, host_log_prefix, ignore_errors=True)
    logger.info(f"{host_log_prefix} {GREEN}Etapa 2/6: Serviços parados/desabilitados.{NC}")

    # --- Etapa 3: Remover Arquivos de Configuração do Sistema ---
    logger.info(f"{host_log_prefix} Etapa 3/6: Removendo arquivos de configuração do sistema...")
    files_to_remove = [
        "/etc/systemd/system/ariusmonitor.service",
        "/etc/systemd/system/ariusmonitor-shutdown.service",
        "/etc/systemd/system/pdvstate.service",
        "/etc/init.d/ariusmonitor",
        "/etc/init.d/pdvstate",
        "/etc/rc.d/rc.ariusmonitor", # Slackware
        "/etc/sudoers.d/ariusmonitor",
        "/etc/cron.d/ariusmonitor-check-service", # Cron legado
        "/etc/cron.d/ariusmonitor-trapper",       # Cron legado
        "/ariusmonitor.tar.gz",
        "/tmp/ariusmonitor.tar.gz"
    ]
    all_removed_ok = True
    for file_path in files_to_remove:
        if not _run_command(session, f"rm -f {file_path}", needs_sudo, logger, host_log_prefix, ignore_errors=True):
             all_removed_ok = False # Mesmo ignorando erro, logamos falha geral se houver

    # Limpa entradas do crontab do usuário root (idempotente)
    _run_command(session, "(crontab -l 2>/dev/null | grep -v '/ariusmonitor') | crontab -", needs_sudo, logger, host_log_prefix, ignore_errors=True)
    
    # Limpa entradas nos scripts rc.d do Slackware (idempotente)
    for rc_file in ["/etc/rc.d/rc.local", "/etc/rc.d/rc.0", "/etc/rc.d/rc.6"]:
        _run_command(session, f"sed -i '/# BEGIN ARIUSMONITOR/,/# END ARIUSMONITOR/d' {rc_file}", needs_sudo, logger, host_log_prefix, ignore_errors=True)

    if is_systemd:
        _run_command(session, "systemctl daemon-reload", needs_sudo, logger, host_log_prefix)
        
    if all_removed_ok:
        logger.info(f"{host_log_prefix} {GREEN}Etapa 3/6: Arquivos de configuração do sistema removidos.{NC}")
    else:
        logger.warning(f"{host_log_prefix} {YELLOW}Etapa 3/6: Alguns arquivos de configuração podem não ter sido removidos.{NC}")


    # --- Etapa 4: Remover Diretório da Aplicação ---
    logger.info(f"{host_log_prefix} Etapa 4/6: Removendo diretório {base_dir}...")
    if not _run_command(session, f"rm -rf {base_dir}", needs_sudo, logger, host_log_prefix):
        logger.error(f"{host_log_prefix} {RED}FALHA CRÍTICA na Etapa 4/6. Não foi possível remover o diretório principal. Abortando.{NC}")
        return # Falha crítica, não tenta remover usuário/grupo
    logger.info(f"{host_log_prefix} {GREEN}Etapa 4/6: Diretório da aplicação removido.{NC}")

    # --- Etapa 5: Remover Usuário ---
    logger.info(f"{host_log_prefix} Etapa 5/6: Removendo usuário ariusmonitor...")
    if not _run_command(session, "userdel ariusmonitor", needs_sudo, logger, host_log_prefix, ignore_errors=True):
         logger.warning(f"{host_log_prefix} {YELLOW}Não foi possível remover o usuário ariusmonitor (pode já não existir).{NC}")
    else:
        logger.info(f"{host_log_prefix} {GREEN}Etapa 5/6: Usuário removido (ou já não existia).{NC}")

    # --- Etapa 6: Remover Grupo ---
    logger.info(f"{host_log_prefix} Etapa 6/6: Removendo grupo ariusmonitor...")
    # Verifica se o grupo está vazio antes de remover, para evitar erros se outros usuários o utilizarem.
    check_group_cmd = "getent group ariusmonitor | cut -d: -f4"
    status, group_users, _ = session.run(check_group_cmd, use_sudo=needs_sudo)
    if status == 0 and not group_users.strip(): # Se o grupo existe E está vazio
        if not _run_command(session, "groupdel ariusmonitor", needs_sudo, logger, host_log_prefix, ignore_errors=True):
            logger.warning(f"{host_log_prefix} {YELLOW}Não foi possível remover o grupo ariusmonitor.{NC}")
        else:
            logger.info(f"{host_log_prefix} {GREEN}Etapa 6/6: Grupo removido (ou já não existia).{NC}")
    elif status != 0:
         logger.info(f"{host_log_prefix} {GREEN}Etapa 6/6: Grupo ariusmonitor já não existia.{NC}")
    else:
         logger.warning(f"{host_log_prefix} {YELLOW}Etapa 6/6: Grupo ariusmonitor ainda possui membros ({group_users.strip()}), não será removido.{NC}")


    logger.info(f"{host_log_prefix} {GREEN}AÇÃO 'pdv_uninstall' FINALIZADA COM SUCESSO.{NC}")