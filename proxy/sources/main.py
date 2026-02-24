#!/usr/bin/env python3

import json
import os
import sys
import argparse
import logging
import psutil
import importlib
from textwrap import dedent
from concurrent.futures import ThreadPoolExecutor, as_completed
from pdv_asset_manager import download_assets_for_action

from utils import setup_logging
from zabbix_client import (
    get_hosts,
    get_triggers,
    get_hosts_by_trigger_ids,
    get_hosts_by_trigger_name,
)
from process_one import process_one
from provider_adapter import (
    resolve_provider,
    translate_action_for_provider,
)
from actions import (
    get_action_version,
    resolve_action_name,
    list_supported_action_names,
)

def list_available_actions():
    """
    Lista os módulos de ação disponíveis na pasta 'actions' (sem extensão .py).
    """
    actions_dir = os.path.join(os.path.dirname(__file__), "actions")
    if not os.path.isdir(actions_dir):
        return []

    module_actions = sorted(
        os.path.splitext(filename)[0]
        for filename in os.listdir(actions_dir)
        if filename.endswith(".py") and not filename.startswith("__")
    )
    return list_supported_action_names(module_actions)

def parse_args():
    """
    Analisa os argumentos da linha de comando. Agora espera uma ação posicional.
    """
    available_actions = list_available_actions()
    actions_help = (
        "Ações disponíveis:\n- " + "\n- ".join(available_actions)
        if available_actions
        else "Nenhuma ação encontrada em 'actions/'."
    )

    parser = argparse.ArgumentParser(
        description=dedent(
            """
            Bot Arius Monitor: executa ações modulares em hosts filtrados pelo Zabbix.
            Informe a ação (nome do módulo em 'actions' sem .py) e os filtros desejados.
            """
        ),
        epilog=actions_help,
        formatter_class=argparse.RawTextHelpFormatter # Melhora a formatação da ajuda
    )
    
    # --- Argumento Principal: A Ação ---
    parser.add_argument(
        'action', 
        type=str, 
        help="Nome da action (canonica ou legada). Exemplos: install_endpoint_agent, pdv_install, shutdown_endpoint."
    )

    # --- Filtros para Selecionar Hosts ---
    parser.add_argument('--debug', action='store_true', help='Imprime logs de debug detalhados')
    parser.add_argument("--rede", type=str, help="Filtro de rede (geralmente preenchido via config)")
    parser.add_argument("--loja", type=str, help="Filtro de loja (ex: LOJA001)")
    parser.add_argument("--pdv", type=str, help="Filtro de PDV (ex: PDV201)")
    parser.add_argument("--pdv-ip", dest="pdv_ip", type=str, help="Filtro de IP do PDV")
    parser.add_argument("--agent-status", dest="agent_status", type=int, help="Filtro de status do agent no Zabbix (0, 1, 2)")
    parser.add_argument(
        "--trigger-id",
        dest="trigger_ids",
        type=str,
        help="IDs de trigger no Zabbix (separados por virgula) para filtrar hosts em problema (pdv_install)."
    )
    parser.add_argument(
        "--trigger-name",
        dest="trigger_name",
        type=str,
        help="Descricao da trigger no Zabbix (match exato) para filtrar hosts em problema (pdv_install)."
    )

    # --- Parâmetros gerais usados por ações específicas ---
    parser.add_argument("--dtini", type=str, help="Data inicial (YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS) para ações de cupons/SAT")
    parser.add_argument("--dtfim", type=str, help="Data final (YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS) para ações de cupons/SAT")

    # --- Argumentos Extras (usados por ações específicas) ---
    parser.add_argument("--cnpj-contribuinte", type=str, help="CNPJ do contribuinte para a ação 'associar_assinatura'")
    parser.add_argument("--chave-assinatura", type=str, help="Chave de assinatura do SAT para a ação 'associar_assinatura'")
    parser.add_argument("--autoregister", action="store_true", help="Cadastra automaticamente hosts ausentes no Zabbix (pdv_auto_register)")
    parser.add_argument("--list-missing", action="store_true", help="Lista hosts ausentes/divergentes no Zabbix (pdv_auto_register)")
    parser.add_argument("--fix-divergent", action="store_true", help="Corrige automaticamente nomes divergentes no Zabbix (pdv_auto_register)")
    parser.add_argument("--list-zabbix-only", action="store_true", help="Lista hosts no Zabbix que não existem no concentrador (pdv_auto_register)")
    parser.add_argument("--timezone", type=str, help="Override do fuso horário para a ação 'pdv_update_timezone' (ex: America/Sao_Paulo)")
    parser.add_argument("--localtime-target", dest="localtime_target", type=str, help="Override do alvo de /etc/localtime (ex: /usr/share/zoneinfo/Etc/GMT+3)")
    parser.add_argument("--enable-ntp", dest="enable_ntp", action="store_true", default=None, help="Habilita sincronização NTP (pdv_update_timezone)")
    parser.add_argument("--ntp-server", dest="ntp_server", type=str, help="Servidor NTP para sincronização (ex: supermercadospaguemenos.com.br)")
    parser.add_argument(
        "--compat-mode",
        dest="compat_mode",
        choices=["off", "warn", "enforce"],
        help="Modo de compatibilidade de endpoint por host (default via config: PARAM_COMPATIBILITY_MODE ou 'warn')."
    )
    parser.add_argument(
        "--provider",
        type=str,
        help="Provider alvo da execução (ex: arius, zanthus). Default via config PARAM_PROVIDER ou 'arius'.",
    )
    
    parser.add_argument("--dry-run", action="store_true", help="Não altera nada nos hosts; apenas resolve templates e mostra o conteúdo que seria aplicado.")

    return parser.parse_args()


def _parse_trigger_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def is_already_running():
    """
    Verifica se já existe outra instância deste mesmo script em execução,
    comparando o interpretador e o caminho do script.
    """
    try:
        current_process = psutil.Process()
        my_script_path = sys.argv[0]
        my_interpreter_path = sys.executable

        # Itera sobre todos os processos
        for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
            # Ignora o processo atual e processos 'zumbis' que não podem ser lidos
            if proc.pid == current_process.pid or proc.status() == psutil.STATUS_ZOMBIE:
                continue

            # Critério 1: O processo está usando o mesmo interpretador Python?
            if proc.info.get('exe') == my_interpreter_path:
                cmdline = proc.info.get('cmdline')
                
                # Critério 2: O processo está executando o mesmo arquivo de script?
                if cmdline and len(cmdline) > 1 and cmdline[1] == my_script_path:
                    # Encontramos outra instância exata do nosso script.
                    return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Ignora erros de processos que morrem durante a iteração
        pass
        
    # Se o loop terminar sem encontrar outra instância, retorna False
    return False


def main():
    # Carrega a configuração principal
    try:
        with open("/ariusmonitor/config_bot.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERRO: Arquivo de configuração '/ariusmonitor/config_bot.json' não encontrado.")
        sys.exit(1)

    args = parse_args()
    logger = setup_logging(config, debug=args.debug)

    # Verifica instâncias concorrentes
    if is_already_running():
        logger.error("Outra instância do bot_ariusmonitor já está em execução.")
        sys.exit(1)

    requested_action = args.action
    args.provider = resolve_provider(config, args)
    provider_translated_action, translated_by_provider = translate_action_for_provider(
        requested_action,
        args.provider,
        logger,
    )

    resolved_action, canonical_action, used_alias = resolve_action_name(provider_translated_action)
    args.requested_action = requested_action
    args.provider_requested_action = provider_translated_action
    args.canonical_action = canonical_action
    args.action = resolved_action

    if translated_by_provider:
        logger.info(
            f"Provider '{args.provider}' traduziu ação '{requested_action}' para '{provider_translated_action}'."
        )

    if used_alias or translated_by_provider:
        logger.info(
            f"Ação recebida '{requested_action}' resolvida para '{resolved_action}' "
            f"(canônica: '{canonical_action}', provider: '{args.provider}')."
        )

    logger.info(f"Ação '{args.action}' versão {get_action_version(args.action)}")
    if args.debug:
        logger.debug(
            f"Ação requisitada '{args.requested_action}' => executada '{args.action}' "
            f"(canônica '{args.canonical_action}') versão {get_action_version(args.action)}"
        )

    logger.info(f"=== INICIANDO BOT ARIUS MONITOR | AÇÃO: '{args.action}' ===")

    # Define quais ações realmente precisam baixar arquivos.
    ACTIONS_REQUIRING_ASSETS = {"pdv_install", "pdv_update_config"}
    LOCAL_ONLY_ACTIONS = {
        "pdv_atualiza_impressora",
        "pdv_auto_register",
        "cupons",
        "cupons_detalhes",
        "cupons_lv",
        "sat_config",
        "status_caixa"
    }

    # Ações locais não iteram hosts via SSH; executam uma única vez com base no config.
    if args.action in LOCAL_ONLY_ACTIONS:
        logger.info("Ação marcada como local. Nenhum host remoto será processado.")
        try:
            action_module = importlib.import_module(f"actions.{args.action}")
        except ImportError:
            logger.critical(f"Ação local '{args.action}' não encontrada no pacote 'actions'.")
            sys.exit(1)

        run_fn = getattr(action_module, "run_local", None) or getattr(action_module, "run", None)
        if not callable(run_fn):
            logger.critical(f"Ação local '{args.action}' não expõe função 'run_local' ou 'run'.")
            sys.exit(1)

        try:
            run_fn(config, logger, args)
        except Exception as e:
            logger.exception(f"Erro ao executar ação local '{args.action}': {e}")
            sys.exit(1)

        logger.info(f"=== FIM DA EXECUÇÃO | AÇÃO LOCAL '{args.action}' ===")
        sys.exit(0)

    # Só executa o download se a ação estiver na lista de pré-requisitos.
    if args.action in ACTIONS_REQUIRING_ASSETS:
        logger.info(f"Ação '{args.action}' requer assets. Iniciando preparação...")
        if not download_assets_for_action(args.action, config):
            logger.critical("Não foi possível baixar os arquivos necessários. Abortando a execução.")
            sys.exit(1)

    # Prepara o dicionário de filtros
    filters = {
        "rede": args.rede or config.get("PARAM_REDE"),
        "loja": args.loja,
        "pdv": args.pdv,
        "pdv_ip": args.pdv_ip,
        "agent_status": args.agent_status
    }

    trigger_ids = _parse_trigger_ids(args.trigger_ids)
    trigger_name = (args.trigger_name or "").strip()

    # Decide a fonte dos hosts com base na ação.
    # No futuro, outras ações especiais podem usar fontes diferentes.
    # NOTA: Por enquanto, a única ação que usa uma fonte diferente é a de credenciais inválidas.
    if args.action == 'fix_invalid_creds':
         logger.info("Obtendo hosts a partir de triggers de 'Credenciais Inválidas'...")
         # IMPORTANTE: A função get_triggers precisa ser ajustada para retornar
         # os hosts no mesmo formato que get_hosts (com ip, user, pass, etc.)
         hosts = get_triggers(config)
    elif (trigger_ids or trigger_name) and args.action == "pdv_install":
        logger.info("Obtendo hosts a partir de triggers no Zabbix...")
        if trigger_ids:
            hosts = get_hosts_by_trigger_ids(config, trigger_ids, agent_status=filters.get("agent_status"))
        else:
            hosts = get_hosts_by_trigger_name(config, trigger_name, agent_status=filters.get("agent_status"))
    else:
        if trigger_ids or trigger_name:
            logger.warning("Parametros --trigger-id/--trigger-name ignorados para a acao atual.")
        logger.info("Obtendo hosts do Zabbix com base nos filtros...")
        hosts = get_hosts(config, filters)

    if not hosts:
        logger.warning("Nenhum host encontrado para processar. Encerrando.")
        sys.exit(0)

    max_threads = int(config.get("max_threads", 50))
    logger.info(f"Processando {len(hosts)} hosts com até {max_threads} threads...")

    # Multithreading para processar os hosts
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        # Cria um futuro para cada host, passando a ação a ser executada via 'args'
        future_to_host = {
            executor.submit(process_one, host, config, args, logger): host
            for host in hosts
        }
        
        processed_count = 0
        for future in as_completed(future_to_host):
            host = future_to_host[future]
            try:
                future.result()  # Pega o resultado (ou exceção) da thread
            except Exception as e:
                # Este 'except' é uma segurança extra, mas os erros já são tratados em process_one
                logger.critical(f"Erro fatal não tratado no processamento do host {host.get('host')}: {e}")
            
            processed_count += 1
            if processed_count % 100 == 0:
                logger.info(f"{processed_count}/{len(hosts)} hosts processados...")

    logger.info(f"=== FIM DA EXECUÇÃO | {len(hosts)} HOSTS PROCESSADOS ===")

if __name__ == "__main__":
    main()
