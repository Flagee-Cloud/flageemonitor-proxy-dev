# actions/pdv_auto_register.py
"""
Ação local para registro automático de hosts PDV no Zabbix.
Baseada no script standalone PDVAutoRegister.py.
"""
import subprocess
import requests
import logging
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _extract_loja_from_arg(loja_arg):
    if loja_arg is None:
        return None
    match = re.search(r"(\\d+)", str(loja_arg))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _extract_loja_pdv(text, rede):
    if not text:
        return None
    pattern = re.compile(
        rf"{re.escape(rede)}\s*[- ]?\(?\s*LOJA\s*(?P<loja>\d{{3}})\s*\)?\s*[- ]*PDV\s*(?P<pdv>\d+)",
        re.IGNORECASE
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group("loja"), match.group("pdv")


def get_zabbix_group_id(session, api_url, rede, logger: logging.Logger):
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
            logger.error(f"Nenhum grupo encontrado com o nome '{rede}'. Verifique PARAM_REDE no config.")
            return None
        groupid = grupos[0]["groupid"]
        logger.debug(f"ID do grupo '{rede}' é {groupid}.")
        return groupid
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao buscar grupo: {e}")
        return None


def get_existing_hosts_map(session, api_url, groupid, logger: logging.Logger):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"output": ["host", "hostid", "name"], "groupids": [groupid], "selectInterfaces": ["ip"]},
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
            display_name = item.get("name")
            hostid = item.get("hostid")
            interfaces = item.get("interfaces", [])
            ip = interfaces[0].get("ip") if interfaces else None
            mapping[nome] = {"ip": ip, "hostid": hostid, "name": display_name}
        logger.debug(f"Encontrados {len(mapping)} hosts existentes no grupo.")
        return mapping
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao buscar hosts: {e}")
        return {}


def get_hosts_from_db(ip_concentrador, usuario, senha, nome_db, loja, logger: logging.Logger):
    logger.info(f"Conectando ao banco de dados no concentrador {ip_concentrador}...")
    consulta = "SELECT sat_fabricante, nroloja, codigo, ip FROM pf_pdv WHERE codigo >= 200"
    if loja:
        consulta += f" AND nroloja = '{loja}'"

    logger.debug(f"Executando consulta: mysql -h{ip_concentrador} ... -e \"{consulta}\"")
    try:
        resultado = subprocess.run(
            ["mysql", f"-h{ip_concentrador}", f"-u{usuario}", f"-p{senha}", nome_db, "-e", consulta, "-B", "-N"],
            capture_output=True,
            text=True,
            check=True,
            timeout=20
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
            if not colunas[3] or colunas[3] == "0.0.0.0":
                continue
            lista_hosts.append({
                "fabricante": colunas[0],
                "nroloja": colunas[1],
                "codigo": colunas[2],
                "ip": colunas[3]
            })
    logger.debug(f"Consulta em {ip_concentrador} retornou {len(lista_hosts)} registros.")
    return lista_hosts


def create_zabbix_host(session, api_url, host_info, config, groupid, logger: logging.Logger):
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
    logger.debug(f"Payload de criação: {payload}")
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


def rename_zabbix_host(session, api_url, hostid, new_host, new_name, logger: logging.Logger):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": {
            "hostid": hostid,
            "host": new_host,
            "name": new_name
        },
        "id": 1
    }
    logger.info(f"Atualizando hostid {hostid} para '{new_host}'...")
    logger.debug(f"Payload de atualização: {payload}")
    try:
        response = session.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        resposta = response.json()
        if resposta.get("error"):
            logger.error(f"Erro da API ao atualizar host {hostid}: {resposta['error']}")
            return False
        logger.info(f"Host atualizado com sucesso: {new_host}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API do Zabbix ao atualizar host: {e}")
        return False


def run_local(config: dict, logger: logging.Logger, args):
    api_url = f"https://{config['PARAM_ZABBIX_SERVER']}/api_jsonrpc.php"
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {config['PARAM_TOKEN']}"
    })

    groupid = get_zabbix_group_id(session, api_url, config["PARAM_REDE"], logger)
    if not groupid:
        logger.error("Não foi possível obter o ID do grupo. Abortando.")
        return

    existing_map = get_existing_hosts_map(session, api_url, groupid, logger)
    ip_to_host = {
        data.get("ip"): {"host": host, "hostid": data.get("hostid")}
        for host, data in existing_map.items()
        if data.get("ip")
    }

    db_name = config.get("DB_NAME", "controle")
    concentradores = config.get("CONCENTRADORES", [])
    if not concentradores:
        if config.get("PARAM_IP_CONCENTRADORES"):
            logger.info("CONCENTRADORES não definido. Usando PARAM_IP_CONCENTRADORES.")
            concentradores = [{"ip": ip} for ip in config["PARAM_IP_CONCENTRADORES"]]
        else:
            logger.warning("Nenhum concentrador definido no arquivo de configuração. Saindo.")
            return

    target_loja = _extract_loja_from_arg(getattr(args, "loja", None))
    expected_hosts = set()
    expected_display_names = set()
    for concentrador in concentradores:
        ip_conc = concentrador.get("ip")
        logger.debug(f"--- Processando concentrador: {ip_conc} ---")

        hosts_db = get_hosts_from_db(
            ip_conc,
            config["DB_USER"],
            config["DB_PASS"],
            db_name,
            target_loja,
            logger
        )
        if not hosts_db:
            logger.debug("Nenhum registro encontrado no DB para os filtros aplicados.")
            continue

        for registro in hosts_db:
            loja_format = f"{int(registro['nroloja']):03d}"
            chave_host = f"{config['PARAM_REDE']}-LOJA{loja_format}-PDV{registro['codigo']}"
            ip_db = registro["ip"]
            expected_hosts.add(chave_host)
            expected_display_names.add(f"{config['PARAM_REDE']} (LOJA{loja_format}) PDV{registro['codigo']}")

            if chave_host not in existing_map:
                if ip_db in ip_to_host:
                    logger.info(
                        f"[DIVERGÊNCIA DE NOME] IP {ip_db} já existe no Zabbix como "
                        f"'{ip_to_host[ip_db]['host']}', mas esperado '{chave_host}'"
                    )
                    if getattr(args, "fix_divergent", False):
                        hostid = ip_to_host[ip_db]["hostid"]
                        new_name = f"{config['PARAM_REDE']} (LOJA{loja_format}) PDV{registro['codigo']}"
                        rename_zabbix_host(session, api_url, hostid, chave_host, new_name, logger)
                else:
                    logger.info(f"[AUSENTE] Concentrador: {ip_conc} | Host: {chave_host} | IP: {ip_db}")

                if getattr(args, "autoregister", False):
                    registro["host"] = chave_host
                    registro["name"] = f"{config['PARAM_REDE']} (LOJA{loja_format}) PDV{registro['codigo']}"
                    create_zabbix_host(session, api_url, registro, config, groupid, logger)
            else:
                ip_zabbix = existing_map.get(chave_host, {}).get("ip")
                if ip_zabbix and ip_zabbix != ip_db:
                    logger.info(f"[IP DIVERGENTE] Host '{chave_host}': Zabbix={ip_zabbix}, DB={ip_db}")

    logger.info("Ação de auto-registro de PDVs finalizada.")

    if getattr(args, "list_zabbix_only", False):
        rede = config["PARAM_REDE"]
        zabbix_only = []
        matched_candidates = 0
        seen_keys = set()
        for host, data in existing_map.items():
            display_name = data.get("name")
            extracted = _extract_loja_pdv(host, rede) or _extract_loja_pdv(display_name, rede)
            if not extracted:
                continue
            matched_candidates += 1
            loja_num, pdv_num = extracted
            key = f"{rede}-LOJA{loja_num}-PDV{pdv_num}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if key not in expected_hosts:
                zabbix_only.append((key, host, display_name, data.get("ip")))

        if getattr(args, "debug", False):
            logger.debug(f"Candidatos Zabbix analisados: {matched_candidates}")
            logger.debug(f"Hosts esperados (DB): {len(expected_hosts)} | Nomes esperados (DB): {len(expected_display_names)}")
            if matched_candidates == 0 and existing_map:
                sample = sorted(list(existing_map.items()))[:5]
                for host, data in sample:
                    logger.debug(f"Exemplo Zabbix: host='{host}' name='{data.get('name')}' ip='{data.get('ip')}'")

        if zabbix_only:
            logger.info("Hosts no Zabbix ausentes no concentrador:")
            for key, host, display_name, ip in sorted(zabbix_only):
                logger.info(f"[SOMENTE ZABBIX] Esperado: {key} | Host: {host} | Nome: {display_name} | IP: {ip}")
        else:
            logger.info("Nenhum host exclusivo do Zabbix encontrado.")
