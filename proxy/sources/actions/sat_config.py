# actions/sat_config.py
"""
Ação local para sincronizar conf_nfce (SAT Config) com o BI.
Baseada no script standalone SatConfig.py.
"""
import json
import mysql.connector
import requests
from datetime import datetime
from pathlib import Path
import logging

SQL_QUERY = """
    SELECT nroloja, ChaveConciliaSat FROM conf_nfce
    WHERE LENGTH(ChaveConciliaSat) = 36
"""


def connect_mysql(host, user, password, database):
    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        connect_timeout=10
    )


def send_to_bi(data_lote, config, debug, logger: logging.Logger):
    url = f"https://{config['PARAM_BI_SERVER']}/sat/config"
    headers = {
        "Authorization": f"Bearer {config['PARAM_TOKEN_BI']}",
        "Content-Type": "application/json"
    }

    if debug:
        logger.debug("Lote enviado (debug): %s", json.dumps(data_lote, indent=2, ensure_ascii=False))

    try:
        response = requests.post(url, json=data_lote, headers=headers, verify=config["PARAM_BI_CERTI_PATH"], timeout=20)
        if response.status_code == 200:
            logger.info(f"Lote enviado com sucesso: {len(data_lote)} registros.")
        else:
            logger.error(f"Erro {response.status_code} ao enviar lote: {response.text}")
    except Exception as e:
        logger.error(f"Erro ao enviar para API: {e}")


def run_local(config: dict, logger: logging.Logger, args):
    debug = bool(getattr(args, "debug", False))
    log_path = Path(config["PARAM_BASE_DIR"]) / "logs" / "sat_config_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as log:
        for host in config.get("PARAM_IP_CONCENTRADORES", []):
            log.write(f"{datetime.now()} - Conectando ao {host}\n")
            try:
                conn = connect_mysql(host, config["DB_USER"], config["DB_PASS"], "controle")
                cursor = conn.cursor()
                cursor.execute(SQL_QUERY)
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"Erro no host {host}: {e}\n")
                logger.error(f"Erro no host {host}: {e}")
                continue

            if not rows:
                log.write(f"{datetime.now()} - Nenhum dado retornado do host {host}\n")
                logger.info(f"Nenhum dado retornado do host {host}")
                continue

            lote = [{"rede": config["PARAM_REDE"], "nroloja": r[0], "chaveSeguranca": r[1]} for r in rows]
            send_to_bi(lote, config, debug, logger)

    logger.info("Sincronização SAT Config finalizada.")
