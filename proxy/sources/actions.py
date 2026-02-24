#!/usr/bin/env python3
"""
Implementação das ações para cada host/processo:
- check_connection
- detect_distro
- detect_architecture
- instalação/atualização do agent
- atualização de SAT
- remoção e força MonitoraSAT
- backup de cupons
- shutdown
- fluxo central em process_one
"""
import logging
from datetime import datetime, timedelta
from ssh_manager import SSHSession
import os
from utils import GREEN, RED, YELLOW, NC
import socket
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError


# NOVA FUNÇÃO PARA TESTE DE CONEXÃO E FLUIDEZ
def test_connection(session: SSHSession, host: dict, logger: logging.Logger):
    """
    Executa um simples comando 'echo' para validar a conexão SSH.
    """
    logger.info(f"Testando conexão com {host['host']}...")
    status, out, _ = session.run("echo 'Conexao estabelecida com sucesso'", logger=logger)
    if status == 0:
        logger.info(f"{GREEN}Sucesso ao conectar em {host['host']}:{NC} {out.strip()}")
    else:
        logger.error(f"{RED}Falha no comando de teste em {host['host']}{NC}")


def check_connection(session: SSHSession, host: dict) -> bool:
    """
    Testa conectividade TCP e SSH básica.
    """
    ip = host['ip']
    port = host['port_ssh']
    cmd = f"timeout 5 bash -c 'echo > /dev/tcp/{ip}/{port}'"
    status, _, _ = session.run(cmd)
    return status == 0


def detect_distro(session: SSHSession) -> tuple[str, str]:
    """
    Identifica distribuição e versão.
    Retorna (distro, version).
    """
    code, out, _ = session.run("which lsb_release && lsb_release -a")
    if code == 0 and "Distributor ID:" in out:
        lines = dict(line.split(':', 1) for line in out.splitlines() if ':' in line)
        return lines.get('Distributor ID', '').strip(), lines.get('Release', '').strip()

    code, out, _ = session.run("cat /etc/slackware-version")
    if code == 0:
        return "Slackware", out.strip().split()[-1]

    return "Unknown", ""


def detect_architecture(session: SSHSession) -> str:
    """
    Retorna arquitetura (i386, amd64 ou nome bruto).
    """
    code, out, _ = session.run("uname -m")
    if code != 0:
        return "unknown"
    arch = out.strip()
    if arch in ('x86_64', 'amd64'):
        return 'amd64'
    if arch.startswith('i') and arch.endswith('86'):
        return 'i386'
    return arch


def install_or_update_agent(session: SSHSession, host: dict, config: dict, args, logger: logging.Logger):
    """
    Instala ou atualiza completamente o pacote Arius Monitor.
    """
    base_dir = config.get('PARAM_BASE_DIR', '/ariusmonitor')

    # 1) Baixar pacotes do repositório antes de tudo
    repo_url = config.get('PARAM_REPO_URL', 'https://repo.ariusmonitor.flagee.cloud')
    logger.info("Baixando pacotes do repositório repo.ariusmonitor")
    session.run(
        f"wget -N -P {base_dir} {repo_url}/ariusmonitor.tar.gz",
        use_sudo=True
    )

    # 2) Enviar e extrair o pacote
    pkg_path = f"{base_dir}/ariusmonitor.tar.gz"
    logger.info(f"Enviando e extraindo pacote em {host['host']}")
    session.run(f"tar zxvf {pkg_path} -C /", use_sudo=True)

    # 3) Parar serviços anteriores
    logger.info("Parando serviços antigos")
    session.run(f"pkill -f {base_dir}/zabbix/sbin/zabbix_agentd || true", use_sudo=True)
    session.run(f"{base_dir}/utilities/stop.sh", use_sudo=True)

    # 4) Setup inicial
    session.run(f"{base_dir}/utilities/setup.sh", use_sudo=True)

    # 5) Após instalação, atualiza configuração
    update_agent_config(session, host, config, args, logger)


def update_agent_config(session: SSHSession, host: dict, config: dict, args, logger: logging.Logger):
    """
    Atualiza configurações do agente Zabbix:
      - recria o zabbix_agentd.conf
      - envia geral.conf para userparameters
      - mata processos antigos
      - reinicia via utilities/start.sh
      com logs automáticos de OK/FALHA para cada comando.
    """
    base   = config.get('PARAM_BASE_DIR', '/ariusmonitor')
    proxy  = config.get('PARAM_PROXY_IP')
    port_zbx = config.get('PARAM_ZABBIX_PORT', 10050)

    # 1) Recria o zabbix_agentd.conf principal
    cfg = os.path.join(base, 'conf', 'zabbix_agentd.conf')
    content = f"""Server={proxy}
ServerActive={proxy}
ListenPort={port_zbx}
LogFile={config.get('PARAM_AGENTD_LOG')}
PidFile={config.get('PARAM_AGENTD_PID')}
Hostname={host['host']}
BufferSize=300
AllowRoot=1
Include={config.get('PARAM_AGENTD_CONF_DIR')}
MaxLinesPerSecond=100
AllowKey=system.run[*]
UnsafeUserParameters=1
Timeout=20
"""
    logger.info(f"Recriando {cfg}")
    session.run(
        f"bash -c 'cat << EOF > {cfg}\n{content}\nEOF'",
        use_sudo=True,
        get_pty=True,
        logger=logger
    )

    # 2) Envia o geral.conf para o host remoto
    local_geral  = config['PARAM_PATH_GERAL_LOCAL']
    remote_geral = config['PARAM_PATH_GERAL_REMOTE']
    if not os.path.isfile(local_geral):
        logger.error(f"Arquivo local geral.conf não encontrado: {local_geral}")
        raise FileNotFoundError(local_geral)
    logger.info(f"Enviando geral.conf → {remote_geral}")
    session.put(local_geral, remote_geral, use_sudo=True)

    # 3) Mata somente o agente Arius Monitor em /ariusmonitor/zabbix
    agent_bin = os.path.join(base, 'zabbix', 'sbin', 'zabbix_agentd')
    logger.info(f"Matando somente {agent_bin} (ignora agent do sistema)")
    # usa pgrep -f para casar todo o comando, não só o nome
    session.run(
        f"pgrep -f '{agent_bin} -c {base}/conf/zabbix_agentd.conf' | xargs -r kill",
        use_sudo=True,
        logger=logger
    )
    # remove o PID antigo
    pid_file = config.get('PARAM_AGENTD_PID')
    session.run(
        f"rm -f {pid_file}",
        use_sudo=True,
        logger=logger
    )


    # 4) Reinicia o agente via utilities/start.sh
    cmd = f"{base}/utilities/start.sh"
    logger.info(f"Iniciando zabbix_agentd com {cmd}")
    session.run(
        cmd,
        use_sudo=True,
        get_pty=True,
        logger=logger
    )

    # 5) Verifica se o agente subiu
    status, out, err = session.run(
        "pgrep -fl zabbix_agentd",
        use_sudo=False,
        logger=logger
    )
    if status == 0:
        logger.info(f"{GREEN}Agente em execução:{NC} {out.strip()}")
    else:
        logger.warning(f"{YELLOW}Agente NÃO encontrado após start.sh{NC}")

    # 6) Opcional: mostra o início do config para conferência
    session.run(
        f"head -n 10 {cfg}",
        use_sudo=True,
        get_pty=True,
        logger=logger
    )

def remove_monitorasat(session: SSHSession, host: dict, logger: logging.Logger):
    logger.info(f"Removendo MonitoraSAT em {host['host']}")
    base = '/ariusmonitor'
    for fname in ['MonitoraSATc', 'MonitoraSATc64', 'MonitoraSAT.sh']:
        session.run(f"rm -f {base}/{fname}", use_sudo=True)


def force_monitorasat(session: SSHSession, host: dict, logger: logging.Logger):
    logger.info(f"Forçando MonitoraSAT em {host['host']}")
    base = '/ariusmonitor'
    session.run(f"{base}/MonitoraSAT.sh", use_sudo=True)


def backup_cupom(session: SSHSession, host: dict, config: dict, logger: logging.Logger):
    logger.info(f"Iniciando backup de cupons em {host['host']}")
    base_dir = '/posnet/NFCEBKP/'
    dest_root = f"/NFCEBKP/{host['host']}"
    for i in range(10):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        src = f"{base_dir}{date}"
        dest = f"{dest_root}/{date}"
        session.run(f"mkdir -p {dest}", use_sudo=True)
        session.run(f"cp -r {src}/* {dest}/", use_sudo=True)


def shutdown_host(session: SSHSession, host: dict, logger: logging.Logger):
    """
    Verifica o horário e, se permitido, desliga o host remotamente.
    """
    hora_atual = datetime.now().hour
    if hora_atual >= 22 or hora_atual <= 6:
        logger.info(f"Horário permitido. Enviando comando de desligamento para {host['host']}...")
        status, out, err = session.run("shutdown -h now", use_sudo=True, logger=logger)
        if status == 0:
            logger.info(f"{GREEN}Comando de desligamento enviado com sucesso para {host['host']}{NC}")
        else:
            logger.error(f"{RED}Falha ao enviar comando de desligamento para {host['host']}{NC}. Erro: {err}")
    else:
        logger.warning(
            f"{YELLOW}Ação de desligamento para {host['host']} ignorada. Fora do horário permitido (horário atual: {hora_atual}h){NC}"
        )


def process_one(host: dict, config: dict, args, logger: logging.Logger):
    """
    Fluxo principal por host:
    - abre SSHSession
    - testa conexão
    - detecta distro/arch
    - escolhe ação
    """
    logger.info(f"Processando {host['host']} ({host['ip']})")
    session = None # Inicializa a variável
    try:
        session = SSHSession(
            host=host['ip'],
            port=host['port_ssh'],
            user=host['user'],
            # BUG CRÍTICO CORRIGIDO AQUI: 'pass' -> 'password'
            password=host['password'],
            timeout=config.get('ssh', {}).get('timeout', 30)
        )

        # AÇÕES DE EXECUÇÃO ÚNICA E PRIORITÁRIA
        if args.test_connection:
            test_connection(session, host, logger)
            return # Encerra após o teste
        
        # LÓGICA DE SHUTDOWN
        if args.shutdown:
            shutdown_host(session, host, logger)
            return # Encerra após a ação de shutdown

        if args.remove_monitorasat:
            remove_monitorasat(session, host, logger)
        elif args.force_monitorasat:
            force_monitorasat(session, host, logger)
        elif args.shutdown:
            # Futuramente, a lógica de desligamento virá aqui.
            # Por enquanto, podemos usar o teste ou deixar um aviso.
            logger.warning(f"Ação --shutdown ainda não implementada. Usando --test-connection para validar.")
            test_connection(session, host, logger)
        elif args.backup_cupom:
            backup_cupom(session, host, config, logger)
        elif args.update_ariusmonitor:
            install_or_update_agent(session, host, config, args, logger)
        elif args.update_ariusmonitor_param:
            update_agent_config(session, host, config, args, logger)
        elif args.update_sat:
            session.run("/ariusmonitor/MonitoraSAT.sh --func AtualizarSoftwareSAT", use_sudo=True)
        elif args.sat_associar_assinatura:
            if args.cnpj_contribuinte and args.chave_assinatura:
                cmd = (f"/ariusmonitor/MonitoraSAT.sh --func AssociarAssinatura "
                       f"--cnpj-contribuinte {args.cnpj_contribuinte} "
                       f"--chave \"{args.chave_assinatura}\"")
                session.run(cmd, use_sudo=True)
            else:
                logger.error("Faltando CNPJ ou chave para associar assinatura")
        else:
            # Ação padrão: se nenhuma ação for especificada, pode-se definir um comportamento
            logger.info(f"Nenhuma ação específica solicitada para {host['host']}. Verificando conexão.")
            test_connection(session, host, logger)

    except NoValidConnectionsError as e:
        logger.error(f"{RED}Falha de conexão de rede em {host['host']} ({host['ip']}:{host['port_ssh']}){NC} - O host pode estar offline ou a porta bloqueada.")
    except AuthenticationException:
        logger.error(f"{RED}Falha de autenticação em {host['host']}{NC} - Verifique o usuário e a senha no Zabbix.")
    except (socket.timeout, TimeoutError):
        logger.error(f"{RED}Timeout ao tentar conectar em {host['host']}{NC} - O host demorou muito para responder.")
    except SSHException as e:
        logger.error(f"{RED}Erro de SSH em {host['host']}{NC} - {e}")
    except Exception as e:
        # Pega qualquer outro erro e exibe de forma limpa
        logger.error(f"{RED}Erro inesperado em {host['host']}{NC}: {type(e).__name__} - {e}")
    
    finally:
        if session:
            session.close()
