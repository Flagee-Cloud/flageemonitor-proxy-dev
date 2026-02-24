# actions/pdv_atualiza_impressora.py
"""
Ação local que atualiza macros de impressora no Zabbix a partir dos concentradores.
Reaproveita a lógica do script standalone PDVAtualizaImpressora.py.
"""
import re
import subprocess
import requests
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_zabbix_group_id(session, api_url, group_name, logger: logging.Logger):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {"output": ["groupid"], "filter": {"name": [group_name]}},
        "id": 1
    }
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


def get_hosts_data_map(session, api_url, groupid, logger: logging.Logger):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["host", "hostid"],
            "groupids": [groupid],
            "selectMacros": ["macro", "value"]
        },
        "id": 1
    }
    logger.info("Mapeando hosts existentes e suas macros no Zabbix...")
    try:
        response = session.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            logger.error(f"API Zabbix retornou um erro ao buscar hosts: {data['error']}")
            return {}
        host_map = {
            host["host"]: {
                "hostid": host["hostid"],
                "macros": host.get("macros", [])
            }
            for host in data.get("result", [])
        }
        logger.info(f"Encontrados {len(host_map)} hosts no grupo.")
        return host_map
    except requests.RequestException as e:
        logger.error(f"Erro de conexão com a API Zabbix ao buscar hosts: {e}")
        return {}


def get_printer_data(ip_concentrador, usuario, senha, nome_db, logger: logging.Logger):
    """Consulta MySQL no concentrador e retorna lista de impressoras."""
    logger.info(f"Coletando dados de impressora do concentrador {ip_concentrador}...")
    consulta = (
        "SELECT pf_hw.codigo, pf_hw.descricao, pf_hw.disp_imp, impnaofiscal.nomelib "
        "FROM pf_hw INNER JOIN impnaofiscal ON impnaofiscal.codigo = pf_hw.codimpnfiscal;"
    )
    try:
        resultado = subprocess.run(
            ["mysql", f"-h{ip_concentrador}", f"-u{usuario}", f"-p{senha}", nome_db, "-e", consulta, "-B", "-N"],
            capture_output=True,
            text=True,
            check=True,
            timeout=20
        )
        linhas = resultado.stdout.strip().splitlines()
        printer_data = []
        for linha in linhas:
            partes = linha.split("\t")
            if len(partes) == 4:
                printer_data.append({
                    "codigo": partes[0],
                    "descricao": partes[1],
                    "disp_imp": partes[2],
                    "nomelib": partes[3]
                })
        logger.info(f"Encontrados {len(printer_data)} registros de impressora em {ip_concentrador}.")
        return printer_data
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"Erro ao consultar MySQL em {ip_concentrador}: {e}")
        return []


def update_zabbix_macros(session, api_url, hostid, hostname, macros, logger: logging.Logger):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": {"hostid": hostid, "macros": macros},
        "id": 1
    }
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


def _extract_loja_from_arg(loja_arg: str):
    if loja_arg is None:
        return None
    match = re.search(r"(\d+)", str(loja_arg))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def run_local(config: dict, logger: logging.Logger, args):
    api_url = f"https://{config['PARAM_ZABBIX_SERVER']}/api_jsonrpc.php"
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {config['PARAM_TOKEN']}"
    })

    group_id = get_zabbix_group_id(session, api_url, config["PARAM_REDE"], logger)
    if not group_id:
        logger.critical("Não foi possível obter o ID do grupo. Abortando execução.")
        return

    zabbix_hosts_data = get_hosts_data_map(session, api_url, group_id, logger)
    if not zabbix_hosts_data:
        logger.warning("Nenhum host encontrado no Zabbix. Nenhuma macro será atualizada.")

    db_name = config.get("DB_NAME", "controle")
    concentradores_a_processar = []
    if config.get("CONCENTRADORES"):
        logger.info("Formato de configuração padrão ('CONCENTRADORES') detectado.")
        concentradores_a_processar = config["CONCENTRADORES"]
    elif config.get("PARAM_IP_CONCENTRADORES"):
        logger.info("Formato alternativo ('PARAM_IP_CONCENTRADORES') detectado. Adaptando...")
        concentradores_a_processar = [{"ip": ip} for ip in config["PARAM_IP_CONCENTRADORES"]]

    target_loja = _extract_loja_from_arg(args.loja) if getattr(args, "loja", None) else None
    parsing_rule = config.get("PDV_PARSING_RULE")

    logger.info(f"Encontrados {len(concentradores_a_processar)} concentradores configurados para processar.")
    if target_loja is not None:
        logger.info(f"Filtro de loja ativo para '{target_loja:03d}'.")

    for concentrador in concentradores_a_processar:
        ip_conc = concentrador.get("ip")
        if not ip_conc:
            logger.warning(f"Entrada de concentrador inválida no config.json, pulando: {concentrador}")
            continue

        logger.info(f"--- INICIANDO PROCESSAMENTO PARA O IP: {ip_conc} ---")
        printer_list = get_printer_data(ip_conc, config["DB_USER"], config["DB_PASS"], db_name, logger)

        logger.info(f"Busca no banco de dados para {ip_conc} retornou {len(printer_list)} registros.")
        if not printer_list:
            logger.info(f"Nenhum registro de impressora encontrado para {ip_conc}, pulando para o próximo IP.")
            continue

        for printer in printer_list:
            loja_num = None
            pdv_num = None
            pdv_codigo_completo = printer["codigo"]

            if parsing_rule and "regex" in parsing_rule and "source_field" in parsing_rule:
                source_text = printer.get(parsing_rule["source_field"], "")
                match = re.search(parsing_rule["regex"], source_text, re.IGNORECASE)
                if match:
                    match_dict = match.groupdict()
                    loja_num = int(match_dict.get("loja_num")) if match_dict.get("loja_num") else None
                    pdv_num = match_dict.get("pdv_num")

            if loja_num is None:
                loja_num = concentrador.get("loja")

            if pdv_num is None:
                pdv_num = pdv_codigo_completo
                if loja_num:
                    prefixo_loja = str(loja_num)
                    if pdv_num.startswith(prefixo_loja):
                        pdv_num = pdv_num[len(prefixo_loja):]

            if not loja_num:
                logger.warning(f"Não foi possível determinar a loja para o registro: {printer}. Pulando.")
                continue

            if target_loja is not None and loja_num != target_loja:
                continue

            loja_format = f"{int(loja_num):03d}"
            try:
                pdv_formatado = f"{int(pdv_num):03d}"
            except (ValueError, TypeError):
                logger.warning(f"Código do PDV '{pdv_num}' não é puramente numérico. Usando como está.")
                pdv_formatado = str(pdv_num)

            hostname = f"{config['PARAM_REDE']}-LOJA{loja_format}-PDV{pdv_formatado}"

            if hostname in zabbix_hosts_data:
                host_data = zabbix_hosts_data[hostname]
                hostid = host_data["hostid"]
                macros_atuais = {m["macro"]: m["value"] for m in host_data["macros"]}
                macros_atuais["{$PDV_IMPRESSORA_PATH}"] = printer["disp_imp"]
                macros_atuais["{$PDV_IMPRESSORA_LIB}"] = printer["nomelib"]
                macros_finais = [{"macro": k, "value": v} for k, v in macros_atuais.items()]

                if getattr(args, "dry_run", False):
                    logger.info(f"[DRY-RUN] Host: {hostname} | ID: {hostid} | Macros: {macros_finais}")
                else:
                    update_zabbix_macros(session, api_url, hostid, hostname, macros_finais, logger)
            else:
                logger.warning(f"Host '{hostname}' (do concentrador {ip_conc}) não foi encontrado no Zabbix.")

    logger.info("Ação de atualização de impressoras concluída.")
