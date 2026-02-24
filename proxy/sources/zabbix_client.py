# zabbix_client.py

import logging
import requests
from urllib3.exceptions import InsecureRequestWarning

# Desabilita warnings de SSL não verificado
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def _call_api(url: str, token: str, payload: dict) -> dict:
    logger = logging.getLogger()
    headers = {
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {token}"
    }
    logger.debug(f"Enviando requisição para Zabbix API: {payload}")
    resp = requests.post(
        url,
        json=payload,
        headers=headers,
        verify=False,
        timeout=30
    )
    resp.raise_for_status()
    response_json = resp.json()
    logger.debug(f"Resposta recebida da Zabbix API: {response_json}")
    return response_json


def get_hosts(config: dict, filters: dict) -> list[dict]:
    logger = logging.getLogger()
    url   = f"https://{config.get('PARAM_ZABBIX_SERVER')}/api_jsonrpc.php"
    token = config.get("PARAM_TOKEN")
    
    if not token or not url:
        logger.error("PARAM_ZABBIX_SERVER ou PARAM_TOKEN não encontrado no config.json.")
        return []

    template_ids_to_exclude = config.get("EXCLUDE_TEMPLATE_IDS", [])
    
    payload = {
        "jsonrpc": "2.0", "method": "host.get", "id": 1,
        "params": {
            "output": ["hostid", "host"],
            "selectParentTemplates": ["templateid"],
            "filter": {"status": "0"}
        }
    }

    search_parts = [config.get('PARAM_REDE', '')]
    if filters.get('loja'):
        search_parts.append(filters['loja'])
    if filters.get('pdv'):
        search_parts.append(filters['pdv'])
    
    if len(search_parts) > 1:
        search_term = "-".join(search_parts)
        if search_term.strip() != "-":
             payload["params"]["search"] = {"host": search_term}
    
    # Adiciona o filtro de 'agent-status' (available) à primeira consulta, se ele for fornecido.
    if filters.get("agent_status") is not None:
        payload["params"]["filter"]["available"] = str(filters["agent_status"])

    logger.info("Etapa 1/3: Buscando hosts e templates para filtragem...")
    response_step1 = _call_api(url, token, payload)
    all_hosts_from_api = response_step1.get("result", [])
    
    # Filtro por Template ID
    template_filtered_hosts = []
    if template_ids_to_exclude:
        exclude_set = set(str(item) for item in template_ids_to_exclude)
        for h in all_hosts_from_api:
            parent_templates = h.get("parentTemplates", [])
            host_template_ids = {str(t.get('templateid')) for t in parent_templates}
            if not host_template_ids.intersection(exclude_set):
                template_filtered_hosts.append(h)
    else:
        template_filtered_hosts = all_hosts_from_api

    # ### INÍCIO DO WORKAROUND: FILTRO POR NOME DE HOST ###
    logger.info("Etapa 2/3: Aplicando workaround de filtro por nome...")
    keywords_to_include = ("PDV", "SELF", "CONCENTRADOR")
    name_filtered_hosts = []
    for h in template_filtered_hosts:
        host_name = h.get('host', '')
        # Verifica se qualquer uma das palavras-chave está no nome do host (ignorando maiúsculas/minúsculas)
        if any(keyword.lower() in host_name.lower() for keyword in keywords_to_include):
            name_filtered_hosts.append(h)
        else:
            logger.debug(f"Host '{host_name}' ignorado pelo filtro de nome (workaround).")
    
    final_host_ids = [h['hostid'] for h in name_filtered_hosts]
    # ### FIM DO WORKAROUND ###

    if not final_host_ids:
        logger.warning("Nenhum host selecionado após todos os filtros.")
        return []
        
    logger.info(f"Etapa 3/3: Buscando detalhes de conexão para {len(final_host_ids)} hosts filtrados...")
    
    payload_step2 = {
        "jsonrpc": "2.0", "method": "host.get", "id": 2,
        "params": {
            "output": ["host"], "hostids": final_host_ids,
            "selectInventory": ["notes"], "selectInterfaces": ["ip", "port"]
        }
    }
    
    response_step2 = _call_api(url, token, payload_step2)
    final_host_details = response_step2.get("result", [])
    
    logger.info(f"{len(final_host_details)} hosts selecionados para processamento.")
    
    hosts = []
    for h in final_host_details:
        if not h.get("interfaces"):
            logger.warning(f"Host '{h.get('host')}' ignorado por não ter interface de rede.")
            continue
            
        iface = h["interfaces"][0]
        inventory_data = h.get("inventory")
        notes = ""
        if isinstance(inventory_data, dict):
            notes = inventory_data.get("notes", "")

        parts = [p.strip() for p in notes.split(",") if p.strip()]
        user      = parts[0] if len(parts) > 0 else ""
        password  = parts[1] if len(parts) > 1 else ""
        port_ssh  = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 22
        port_zabbix = int(iface.get("port", 10050))

        hosts.append({
            "host":        h["host"], "ip": iface.get("ip", ""), "user": user,
            "password":    password, "port_ssh": port_ssh, "port_zabbix": port_zabbix
        })

    return hosts


def get_triggers(config: dict, filters: dict = None) -> list[dict]:
    logger = logging.getLogger()
    if not filters or not filters.get("credenciais_invalidas"):
        return []

    # --- CORREÇÃO: Usar .get() para acesso seguro, como em get_hosts ---
    url   = f"https://{config.get('PARAM_ZABBIX_SERVER')}/api_jsonrpc.php"
    token = config.get("PARAM_TOKEN")

    if not token or not url:
        logger.error("PARAM_ZABBIX_SERVER ou PARAM_TOKEN não encontrado no config.json.")
        return []

    payload = {
        "jsonrpc": "2.0",
        "method":  "trigger.get",
        "params": {
            "output":         ["description", "status"],
            "filter": {
                "description": "PDV (Credenciais Inválidas)",
                "value":       "1"
            },
            "selectHosts":       ["hostid", "host"],
            "expandDescription": True
        },
        "id": 2
    }

    logger.info("Obtendo triggers de credenciais inválidas do Zabbix...")
    response = _call_api(url, token, payload)

    triggers = []
    for trig in response.get("result", []):
        desc   = trig.get("description", "")
        status = trig.get("status", "")
        for host in trig.get("hosts", []):
            triggers.append({
                "hostid":      host.get("hostid"),
                "host":        host.get("host"),
                "description": desc,
                "status":      status
            })

    return triggers


def get_hosts_by_trigger_ids(config: dict, trigger_ids: list[str], agent_status: int | None = None) -> list[dict]:
    logger = logging.getLogger()
    if not trigger_ids:
        return []

    url = f"https://{config.get('PARAM_ZABBIX_SERVER')}/api_jsonrpc.php"
    token = config.get("PARAM_TOKEN")

    if not token or not url:
        logger.error("PARAM_ZABBIX_SERVER ou PARAM_TOKEN não encontrado no config.json.")
        return []

    payload = {
        "jsonrpc": "2.0",
        "method": "trigger.get",
        "params": {
            "output": ["triggerid", "value"],
            "triggerids": trigger_ids,
            "filter": {"value": "1"},
            "selectHosts": ["hostid", "host"],
        },
        "id": 3,
    }

    logger.info("Obtendo hosts com triggers em problema no Zabbix...")
    response = _call_api(url, token, payload)

    host_ids = []
    for trig in response.get("result", []):
        for host in trig.get("hosts", []):
            host_id = host.get("hostid")
            if host_id:
                host_ids.append(host_id)

    host_ids = sorted(set(host_ids))
    if not host_ids:
        logger.warning("Nenhum host encontrado para os triggerids informados.")
        return []

    host_filter = {"status": "0"}
    if agent_status is not None:
        host_filter["available"] = str(agent_status)

    payload_hosts = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "id": 4,
        "params": {
            "output": ["host"],
            "hostids": host_ids,
            "selectInventory": ["notes"],
            "selectInterfaces": ["ip", "port"],
            "filter": host_filter,
        },
    }

    response_hosts = _call_api(url, token, payload_hosts)
    host_details = response_hosts.get("result", [])

    keywords_to_include = ("PDV", "SELF", "CONCENTRADOR")
    hosts = []
    for h in host_details:
        host_name = h.get("host", "")
        if not any(keyword.lower() in host_name.lower() for keyword in keywords_to_include):
            logger.debug("Host '%s' ignorado pelo filtro de nome (triggerids).", host_name)
            continue

        if not h.get("interfaces"):
            logger.warning("Host '%s' ignorado por não ter interface de rede.", host_name)
            continue

        iface = h["interfaces"][0]
        inventory_data = h.get("inventory")
        notes = ""
        if isinstance(inventory_data, dict):
            notes = inventory_data.get("notes", "")

        parts = [p.strip() for p in notes.split(",") if p.strip()]
        user = parts[0] if len(parts) > 0 else ""
        password = parts[1] if len(parts) > 1 else ""
        port_ssh = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 22
        port_zabbix = int(iface.get("port", 10050))

        hosts.append(
            {
                "host": h["host"],
                "ip": iface.get("ip", ""),
                "user": user,
                "password": password,
                "port_ssh": port_ssh,
                "port_zabbix": port_zabbix,
            }
        )

    logger.info("%s hosts selecionados via triggerids.", len(hosts))
    return hosts


def get_hosts_by_trigger_name(config: dict, trigger_name: str, agent_status: int | None = None) -> list[dict]:
    logger = logging.getLogger()
    if not trigger_name:
        return []

    url = f"https://{config.get('PARAM_ZABBIX_SERVER')}/api_jsonrpc.php"
    token = config.get("PARAM_TOKEN")

    if not token or not url:
        logger.error("PARAM_ZABBIX_SERVER ou PARAM_TOKEN não encontrado no config.json.")
        return []

    payload = {
        "jsonrpc": "2.0",
        "method": "trigger.get",
        "params": {
            "output": ["triggerid", "value", "description"],
            "filter": {"description": trigger_name, "value": "1"},
            "selectHosts": ["hostid", "host"],
            "expandDescription": True,
        },
        "id": 5,
    }

    logger.info("Obtendo hosts com triggers em problema no Zabbix (descricao exata)...")
    response = _call_api(url, token, payload)

    host_ids = []
    for trig in response.get("result", []):
        for host in trig.get("hosts", []):
            host_id = host.get("hostid")
            if host_id:
                host_ids.append(host_id)

    host_ids = sorted(set(host_ids))
    if not host_ids:
        logger.warning("Nenhum host encontrado para a descricao informada.")
        return []

    host_filter = {"status": "0"}
    if agent_status is not None:
        host_filter["available"] = str(agent_status)

    payload_hosts = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "id": 6,
        "params": {
            "output": ["host"],
            "hostids": host_ids,
            "selectInventory": ["notes"],
            "selectInterfaces": ["ip", "port"],
            "filter": host_filter,
        },
    }

    response_hosts = _call_api(url, token, payload_hosts)
    host_details = response_hosts.get("result", [])

    keywords_to_include = ("PDV", "SELF", "CONCENTRADOR")
    hosts = []
    for h in host_details:
        host_name = h.get("host", "")
        if not any(keyword.lower() in host_name.lower() for keyword in keywords_to_include):
            logger.debug("Host '%s' ignorado pelo filtro de nome (trigger-name).", host_name)
            continue

        if not h.get("interfaces"):
            logger.warning("Host '%s' ignorado por não ter interface de rede.", host_name)
            continue

        iface = h["interfaces"][0]
        inventory_data = h.get("inventory")
        notes = ""
        if isinstance(inventory_data, dict):
            notes = inventory_data.get("notes", "")

        parts = [p.strip() for p in notes.split(",") if p.strip()]
        user = parts[0] if len(parts) > 0 else ""
        password = parts[1] if len(parts) > 1 else ""
        port_ssh = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 22
        port_zabbix = int(iface.get("port", 10050))

        hosts.append(
            {
                "host": h["host"],
                "ip": iface.get("ip", ""),
                "user": user,
                "password": password,
                "port_ssh": port_ssh,
                "port_zabbix": port_zabbix,
            }
        )

    logger.info("%s hosts selecionados via descricao de trigger.", len(hosts))
    return hosts
