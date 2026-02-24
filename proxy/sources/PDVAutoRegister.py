#!/usr/bin/env python3
# PDVAutoRegister.py - Registro automático de hosts PDV no Zabbix

import json
import argparse
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import requests
import sys
import urllib3

# Desabilita avisos de HTTPS não verificado, caso esteja com session.verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(path):
    """Carrega o arquivo de configuração JSON."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro fatal ao carregar arquivo de configuração '{path}': {e}")
        sys.exit(1)


def setup_logging(config, list_mode=False, debug_mode=False):
    """Configura o sistema de logs, com nível ajustável."""
    log_path = config.get("logfiles", {}).get("general", "PDVAutoRegister.log")
    rotation = config.get("log_rotation", {})
    max_bytes = rotation.get("max_bytes", 10485760)
    backup_count = rotation.get("backup_count", 5)

    logger = logging.getLogger("PDVAutoRegister")
    
    # Define o nível principal do logger
    if debug_mode:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Handler para o arquivo de log
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Handler para o console (saída padrão)
    if not list_mode:
        console_handler = logging.StreamHandler(sys.stdout)
        # Define o nível do console baseado no modo debug
        if debug_mode:
            console_handler.setLevel(logging.DEBUG)
        else:
            console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

    return logger


def get_zabbix_group_id(session, api_url, rede, logger):
    """Obtém o ID do grupo de hosts no Zabbix."""
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {"output": ["groupid"], "filter": {"name": [rede]}},
        "id": 1
    }
    logger.info(f"Obtendo ID do grupo '{rede}' no Zabbix...")
    try:
        response = session.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        grupos = data.get("result")
        if not grupos:
            logger.error(f"Nenhum grupo encontrado com o nome '{rede}'. Verifique o parâmetro PARAM_REDE no config.")
            sys.exit(1)
        groupid = grupos[0]["groupid"]
        logger.debug(f"ID do grupo '{rede}' é {groupid}.")
        return groupid
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao buscar grupo: {e}")
        sys.exit(1)


def get_existing_hosts_map(session, api_url, groupid, logger):
    """Obtém um mapa de 'nome_do_host -> ip' para hosts já existentes no Zabbix."""
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"output": ["host"], "groupids": [groupid], "selectInterfaces": ["ip"]},
        "id": 1
    }
    logger.info("Obtendo lista de hosts existentes no Zabbix...")
    try:
        response = session.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        mapping = {}
        for item in data.get("result", []):
            nome = item.get("host")
            interfaces = item.get("interfaces", [])
            if interfaces:
                ip = interfaces[0].get("ip")
                mapping[nome] = ip
        logger.debug(f"Encontrados {len(mapping)} hosts existentes no grupo.")
        return mapping
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao buscar hosts: {e}")
        return {} # Retorna mapa vazio para evitar que o script pare


def get_hosts_from_db(ip_concentrador, usuario, senha, nome_db, loja, logger):
    """Consulta o banco de dados de um concentrador para obter a lista de PDVs."""
    logger.info(f"Conectando ao banco de dados no concentrador {ip_concentrador}...")
    consulta = "SELECT sat_fabricante, nroloja, codigo, ip FROM pf_pdv"
    if loja:
        consulta += f" WHERE nroloja = '{loja}'"
    
    logger.debug(f"Executando consulta: mysql -h{ip_concentrador} ... -e \"{consulta}\"")
    
    try:
        resultado = subprocess.run(
            ["mysql", f"-h{ip_concentrador}", f"-u{usuario}", f"-p{senha}", nome_db, "-e", consulta, "-B", "-N"],
            capture_output=True, text=True, check=True, timeout=20
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao executar consulta MySQL em {ip_concentrador}: {e.stderr.strip()}")
        return []
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout ao tentar consultar o banco de dados em {ip_concentrador}.")
        return []
        
    linhas = resultado.stdout.strip().splitlines()
    lista_hosts = []
    for linha in linhas:
        colunas = linha.split("\t")
        if len(colunas) == 4:
            lista_hosts.append({
                "fabricante": colunas[0],
                "nroloja": colunas[1],
                "codigo": colunas[2],
                "ip": colunas[3]
            })
    logger.debug(f"Consulta em {ip_concentrador} retornou {len(lista_hosts)} registros.")
    return lista_hosts


def create_zabbix_host(session, api_url, host_info, config, groupid, logger):
    """Cria um novo host no Zabbix via API."""
    nome_host = host_info["host"]
    interface = {
        "type": 1, "main": 1, "useip": 1,
        "ip": host_info["ip"], "dns": "",
        "port": str(config.get("PARAM_ZABBIX_PORT", 10050))
    }
    macros = [{"macro": "{$SAT_FABRICANTE}", "value": host_info["fabricante"], "description": ""}]
    payload = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": nome_host,
            "name": host_info["name"],
            "interfaces": [interface],
            "inventory_mode": 0,
            "proxy_hostid": config["PARAM_ZABBIX_PROXYID"],
            "groups": [{"groupid": groupid}],
            "tags": [{"tag": "PDV_TIPO", "value": "PDV_PADRAO"}],
            "templates": [{"templateid": tid} for tid in config.get("PARAM_TEMPLATES", ["10543", "10552"])],
            "macros": macros
        },
        "id": 1
    }
    logger.info(f"Enviando requisição para criar host '{nome_host}' no Zabbix...")
    logger.debug(f"Payload de criação: {json.dumps(payload, indent=2)}")
    try:
        response = session.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        resposta = response.json()
        if resposta.get("error"):
            logger.error(f"Erro da API ao criar host {nome_host}: {resposta['error']}")
            return False
        logger.info(f"Host criado com sucesso: {nome_host}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao criar host: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Registro automático de hosts PDV no Zabbix")
    parser.add_argument("--config-file", default="/ariusmonitor/config_bot.json", help="Caminho do arquivo de configuração JSON")
    parser.add_argument("--loja", type=int, help="Número da loja para filtro (opcional)")
    parser.add_argument("--autoregister", action="store_true", help="Cadastrar automaticamente hosts ausentes")
    parser.add_argument("--list-missing", action="store_true", help="Listar hosts ausentes e divergentes no Zabbix")
    parser.add_argument("--debug", action="store_true", help="Habilita modo de depuração com logs detalhados no console")
    args = parser.parse_args()

    config = load_config(args.config_file)
    logger = setup_logging(config, list_mode=args.list_missing, debug_mode=args.debug)
    
    logger.debug("--- SCRIPT INICIADO EM MODO DEBUG ---")

    api_url = f"https://{config['PARAM_ZABBIX_SERVER']}/api_jsonrpc.php"
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {config['PARAM_TOKEN']}"
    })
    logger.debug("Sessão com a API do Zabbix configurada.")

    groupid = get_zabbix_group_id(session, api_url, config["PARAM_REDE"], logger)
    existing_map = get_existing_hosts_map(session, api_url, groupid, logger)
    ip_to_host = {ip: host for host, ip in existing_map.items() if ip}

    db_name = config.get("DB_NAME", "controle")
    
    concentradores = config.get("CONCENTRADORES", [])
    logger.debug(f"Concentradores a serem verificados: {[c.get('ip') for c in concentradores]}")

    if not concentradores:
        logger.warning("Nenhum concentrador definido no arquivo de configuração. Saindo.")
        sys.exit(0)

    for concentrador in concentradores:
        ip_conc = concentrador.get("ip")
        logger.debug(f"\n--- Processando concentrador: {ip_conc} ---")
        
        hosts_db = get_hosts_from_db(ip_conc, config["DB_USER"], config["DB_PASS"], db_name, args.loja, logger)

        if not hosts_db:
            logger.debug(f"Nenhum registro encontrado no DB para os filtros aplicados. Pulando para o próximo.")
            continue

        for registro in hosts_db:
            loja_format = f"{int(registro['nroloja']):03d}"
            chave_host = f"{config['PARAM_REDE']}-LOJA{loja_format}-PDV{registro['codigo']}"
            ip_db = registro['ip']

            if chave_host not in existing_map:
                if ip_db in ip_to_host:
                    print(f"[DIVERGÊNCIA DE NOME] IP {ip_db} já existe no Zabbix como '{ip_to_host[ip_db]}', mas esperado '{chave_host}'")
                else:
                    print(f"[AUSENTE] Concentrador: {ip_conc} | Host: {chave_host} | IP: {ip_db}")

                if args.autoregister:
                    registro['host'] = chave_host
                    registro['name'] = f"{config['PARAM_REDE']} (LOJA{loja_format}) PDV{registro['codigo']}"
                    create_zabbix_host(session, api_url, registro, config, groupid, logger)
            else:
                ip_zabbix = existing_map.get(chave_host)
                if ip_zabbix and ip_zabbix != ip_db:
                    print(f"[IP DIVERGENTE] Host '{chave_host}': Zabbix={ip_zabbix}, DB={ip_db}")
    
    logger.debug("--- SCRIPT FINALIZADO ---")

if __name__ == "__main__":
    main()