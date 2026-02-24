#!/usr/bin/env python3
# PDVAtualizaImpressora.py - v2.1 - Corrigido fallback para modo single_shop.

import json
import argparse
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import requests
import sys
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_config(path):
    """Carrega o arquivo de configuração JSON."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro fatal ao carregar o arquivo de configuração '{path}': {e}")
        sys.exit(1)

def setup_logging(config):
    """Configura o sistema de logging para gravar em arquivo e exibir no console."""
    log_path = config.get("logfiles", {}).get("general", "update_macros.log")
    rotation = config.get("log_rotation", {})
    max_bytes = rotation.get("max_bytes", 10485760)
    backup_count = rotation.get("backup_count", 5)
    logger = logging.getLogger("UpdatePrinterMacros")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)
    return logger

def get_zabbix_group_id(session, api_url, group_name, logger):
    """Obtém o ID de um grupo de hosts no Zabbix pelo nome."""
    payload = {"jsonrpc": "2.0", "method": "hostgroup.get", "params": {"output": ["groupid"], "filter": {"name": [group_name]}}, "id": 1}
    logger.info(f"Buscando ID do grupo '{group_name}' no Zabbix...")
    try:
        response = session.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            logger.error(f"API Zabbix retornou um erro ao buscar grupo: {data['error']}")
            return None
        groups = data.get("result")
        if not groups:
            logger.error(f"Nenhum grupo encontrado com o nome '{group_name}'")
            return None
        group_id = groups[0]["groupid"]
        logger.info(f"ID do grupo '{group_name}' é: {group_id}")
        return group_id
    except requests.RequestException as e:
        logger.error(f"Erro de conexão com a API Zabbix: {e}")
        return None

def get_hosts_data_map(session, api_url, groupid, logger):
    """Cria um mapa de 'hostname' -> {'hostid': ..., 'macros': ...}."""
    payload = {"jsonrpc": "2.0", "method": "host.get", "params": {"output": ["host", "hostid"], "groupids": [groupid], "selectMacros": ["macro", "value"]}, "id": 1}
    logger.info("Mapeando hosts existentes e suas macros no Zabbix...")
    try:
        response = session.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            logger.error(f"API Zabbix retornou um erro ao buscar hosts: {data['error']}")
            return {}
        host_map = {host['host']: {'hostid': host['hostid'], 'macros': host.get('macros', [])} for host in data.get("result", [])}
        logger.info(f"Encontrados {len(host_map)} hosts no grupo.")
        return host_map
    except requests.RequestException as e:
        logger.error(f"Erro de conexão com a API Zabbix ao buscar hosts: {e}")
        return {}

def get_printer_data(ip_concentrador, usuario, senha, nome_db, logger):
    """Função de coleta de dados unificada."""
    logger.info(f"Coletando dados de impressora do concentrador {ip_concentrador}...")
    consulta = ("SELECT pf_hw.codigo, pf_hw.descricao, pf_hw.disp_imp, impnaofiscal.nomelib FROM pf_hw INNER JOIN impnaofiscal ON impnaofiscal.codigo = pf_hw.codimpnfiscal;")
    try:
        resultado = subprocess.run(["mysql", f"-h{ip_concentrador}", f"-u{usuario}", f"-p{senha}", nome_db, "-e", consulta, "-B", "-N"], capture_output=True, text=True, check=True, timeout=20)
        linhas = resultado.stdout.strip().splitlines()
        printer_data = []
        for linha in linhas:
            partes = linha.split("\t")
            if len(partes) == 4:
                printer_data.append({'codigo': partes[0], 'descricao': partes[1], 'disp_imp': partes[2], 'nomelib': partes[3]})
        logger.info(f"Encontrados {len(printer_data)} registros de impressora em {ip_concentrador}.")
        return printer_data
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"Erro ao consultar MySQL em {ip_concentrador}: {e}")
        return []

def update_zabbix_macros(session, api_url, hostid, hostname, macros, logger):
    """Atualiza as macros de um host específico no Zabbix."""
    payload = {"jsonrpc": "2.0", "method": "host.update", "params": {"hostid": hostid, "macros": macros}, "id": 1}
    logger.info(f"Atualizando macros para o host '{hostname}' (ID: {hostid})...")
    try:
        response = session.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        resposta = response.json()
        if "error" in resposta:
            logger.error(f"Erro ao atualizar host '{hostname}': {resposta['error']}")
        else:
            logger.info(f"Macros atualizadas com sucesso para '{hostname}'.")
    except requests.RequestException as e:
        logger.error(f"Erro de conexão ao tentar atualizar macros para '{hostname}': {e}")

def main():
    """Função principal que orquestra a execução do script."""
    parser = argparse.ArgumentParser(description="Atualiza macros de impressora para hosts PDV no Zabbix.")
    parser.add_argument("--config-file", default="/ariusmonitor/config_bot.json", help="Caminho do arquivo de configuração JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Roda em modo debug (dry run) sem alterar o Zabbix.")
    parser.add_argument("--loja", type=int, help="Processa apenas a loja especificada (ex: 1 para LOJA001).")
    args = parser.parse_args()

    config = load_config(args.config_file)
    logger = setup_logging(config)
    
    if args.dry_run:
        logger.info("="*35 + "\nMODO DEBUG (DRY-RUN) ATIVADO\nNenhuma alteração será feita no Zabbix.\n" + "="*35)
    if args.loja:
        logger.info(f"FILTRO POR LOJA ATIVADO: Apenas a loja {args.loja} sera processada.")

    api_url = f"https://{config['PARAM_ZABBIX_SERVER']}/api_jsonrpc.php"
    session = requests.Session()
    session.verify = False
    session.headers.update({"Content-Type": "application/json-rpc", "Authorization": f"Bearer {config['PARAM_TOKEN']}"})
    
    group_id = get_zabbix_group_id(session, api_url, config["PARAM_REDE"], logger)
    if not group_id:
        logger.critical("Não foi possível obter o ID do grupo. Abortando execução.")
        sys.exit(1)
        
    zabbix_hosts_data = get_hosts_data_map(session, api_url, group_id, logger)
    if not zabbix_hosts_data:
        logger.warning("Nenhum host encontrado no Zabbix. O script continuará, mas nenhuma macro será atualizada.")

    db_name = config.get("DB_NAME", "controle")

    concentradores_a_processar = []
    if "CONCENTRADORES" in config and config["CONCENTRADORES"]:
        logger.info("Formato de configuracao padrao ('CONCENTRADORES') detectado.")
        concentradores_a_processar = config["CONCENTRADORES"]
    elif "PARAM_IP_CONCENTRADORES" in config and config["PARAM_IP_CONCENTRADORES"]:
        logger.info("Formato de configuracao alternativo ('PARAM_IP_CONCENTRADORES') detectado. Adaptando...")
        concentradores_a_processar = [{"ip": ip} for ip in config["PARAM_IP_CONCENTRADORES"]]
    
    logger.info(f"Encontrados {len(concentradores_a_processar)} concentradores no arquivo de configuracao para processar.")
    
    parsing_rule = config.get("PDV_PARSING_RULE")
    if parsing_rule:
        logger.info(f"Regra de parsing personalizada encontrada. Fonte: '{parsing_rule.get('source_field')}', Regex: '{parsing_rule.get('regex')}'")
    else:
        logger.warning("NENHUMA REGRA DE PARSING ('PDV_PARSING_RULE') encontrada na configuracao. Usando logica padrao.")

    for concentrador in concentradores_a_processar:
        ip_conc = concentrador.get("ip")
        if not ip_conc:
            logger.warning(f"Entrada de concentrador invalida no config.json, pulando: {concentrador}")
            continue

        logger.info(f"--- INICIANDO PROCESSAMENTO PARA O IP: {ip_conc} ---")
        printer_list = get_printer_data(ip_conc, config["DB_USER"], config["DB_PASS"], db_name, logger)
        
        logger.info(f"Busca no banco de dados para {ip_conc} retornou {len(printer_list)} registros.")
        if not printer_list:
            logger.info(f"Nenhum registro de impressora encontrado para {ip_conc}, pulando para o proximo IP.")
            continue

        for printer in printer_list:
            loja_num = None
            pdv_num = None
            pdv_codigo_completo = printer['codigo']

            # --- LÓGICA DE DESCOBERTA DA LOJA CORRIGIDA ---
            # Estratégia 1: Tenta usar a regra de parsing, se existir.
            if parsing_rule and "regex" in parsing_rule and "source_field" in parsing_rule:
                source_text = printer.get(parsing_rule["source_field"], "")
                match = re.search(parsing_rule["regex"], source_text, re.IGNORECASE)
                if match:
                    match_dict = match.groupdict()
                    loja_num = int(match_dict.get('loja_num')) if match_dict.get('loja_num') else None
                    pdv_num = match_dict.get('pdv_num')
            
            # Estratégia 2 (Fallback): Se a regra não encontrou a loja, tenta o modo single_shop.
            if loja_num is None:
                loja_num = concentrador.get("loja")

            if pdv_num is None:
                pdv_num = pdv_codigo_completo
                if loja_num:
                    prefixo_loja = str(loja_num)
                    if pdv_num.startswith(prefixo_loja):
                        pdv_num = pdv_num[len(prefixo_loja):]
            
            if not loja_num:
                logger.warning(f"Nao foi possivel determinar a loja para o registro: {printer}. Pulando.")
                continue

            if args.loja is not None and loja_num != args.loja:
                continue

            loja_format = f"{int(loja_num):03d}"
            
            try:
                pdv_formatado = f"{int(pdv_num):03d}"
            except (ValueError, TypeError):
                logger.warning(f"Código do PDV '{pdv_num}' não é puramente numérico. Usando como está.")
                pdv_formatado = pdv_num

            hostname = f"{config['PARAM_REDE']}-LOJA{loja_format}-PDV{pdv_formatado}"

            if hostname in zabbix_hosts_data:
                host_data = zabbix_hosts_data[hostname]
                hostid = host_data['hostid']
                macros_atuais = {m['macro']: m['value'] for m in host_data['macros']}
                macros_atuais['{$PDV_IMPRESSORA_PATH}'] = printer['disp_imp']
                macros_atuais['{$PDV_IMPRESSORA_LIB}'] = printer['nomelib']
                macros_finais = [{"macro": k, "value": v} for k, v in macros_atuais.items()]

                if args.dry_run:
                    logger.info(f"[DRY-RUN] Host: {hostname} | ID: {hostid}")
                    #logger.info(f"[DRY-RUN] PAYLOAD DE MACROS A SER ENVIADO:\n{json.dumps(macros_finais, indent=2)}")
                else:
                    update_zabbix_macros(session, api_url, hostid, hostname, macros_finais, logger)
            else:
                logger.warning(f"Host '{hostname}' (do concentrador {ip_conc}) não foi encontrado no Zabbix.")
    
    logger.info("Script concluído.")

if __name__ == "__main__":
    main()