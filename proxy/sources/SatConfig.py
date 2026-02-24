#!/usr/bin/env python3
import mysql.connector
import json
import requests
from datetime import datetime
from pathlib import Path

# Carrega configuração
with open("/ariusmonitor/config_bot.json") as f:
    config = json.load(f)

DB_USER = config["DB_USER"]
DB_PASS = config["DB_PASS"]
TOKEN_BI = config["PARAM_TOKEN_BI"]
REDE = config["PARAM_REDE"]
CERT_PATH = config["PARAM_BI_CERTI_PATH"]

LOG_PATH = Path(config["PARAM_BASE_DIR"]) / "logs" / "sat_config_log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

SQL_QUERY = """
    SELECT nroloja, ChaveConciliaSat FROM conf_nfce
    WHERE LENGTH(ChaveConciliaSat) = 36
"""

def connect_mysql(host, database):
    return mysql.connector.connect(
        host=host,
        user=DB_USER,
        password=DB_PASS,
        database=database,
        connect_timeout=10
    )

def send_to_bi(data_lote, debug=False):
    url = f"https://{config['PARAM_BI_SERVER']}/sat/config"
    headers = {
        "Authorization": f"Bearer {TOKEN_BI}",
        "Content-Type": "application/json"
    }

    if debug:
        print("\n=== LOTE ENVIADO ===")
        print(json.dumps(data_lote, indent=2, ensure_ascii=False))
        print("=====================\n")

    try:
        response = requests.post(url, json=data_lote, headers=headers, verify=CERT_PATH, timeout=20)
        if response.status_code == 200:
            print(f"Lote enviado com sucesso: {len(data_lote)} registros.")
        else:
            print(f"Erro {response.status_code} ao enviar lote: {response.text}")
    except Exception as e:
        print(f"Erro ao enviar para API: {e}")

import argparse
parser = argparse.ArgumentParser(description="Sincroniza conf_nfce (SAT Config) com BI")
parser.add_argument("--debug", "-d", action="store_true", help="Habilita modo de depuração")
args = parser.parse_args()

def main():
    with open(LOG_PATH, 'a') as log:
        for host in config["PARAM_IP_CONCENTRADORES"]:
            log.write(f"{datetime.now()} - Conectando ao {host}\n")
            try:
                conn = connect_mysql(host, "controle")
                cursor = conn.cursor()
                cursor.execute(SQL_QUERY)
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"Erro no host {host}: {e}\n")
                continue

            if not rows:
                log.write(f"{datetime.now()} - Nenhum dado retornado do host {host}\n")
                continue

            lote = [{"rede": REDE, "nroloja": r[0], "chaveSeguranca": r[1]} for r in rows]
            send_to_bi(lote, debug=args.debug)

if __name__ == "__main__":
    main()