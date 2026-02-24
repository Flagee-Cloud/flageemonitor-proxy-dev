#!/usr/bin/env python3
# coding: utf-8

import os
import sys
from pathlib import Path
import psutil

def already_running():
    """
    Retorna True se já existir outra instância Python rodando exatamente este script.
    """
    me_pid    = os.getpid()
    me_script = str(Path(__file__).resolve())
    me_python = sys.executable

    for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
        try:
            pid = proc.info['pid']
            if pid == me_pid:
                continue
            exe     = proc.info.get('exe')     or ''
            cmdline = proc.info.get('cmdline') or []
            # só considera processos Python com mesmo executável e mesmo script
            if exe == me_python and len(cmdline) >= 2:
                script_path = str(Path(cmdline[1]).resolve())
                if script_path == me_script:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

if already_running():
    print("Script já está em execução em outro processo.")
    sys.exit(1)

# —————— Imports e parser de argumentos ——————
import json
import requests
import subprocess
import mysql.connector
import argparse
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser(description="Sincroniza promoções de produtos com o BI")
parser.add_argument("--debug", "-d", action="store_true", help="Modo depuração")
args = parser.parse_args()
debug = args.debug

# —————— Carrega configuração ——————
config = json.load(open("/ariusmonitor/config_bot.json"))

DB_USER    = config["DB_USER"]
DB_PASS    = config["DB_PASS"]
REDE       = config["PARAM_REDE"]
EMPRESA_ID = config.get("PARAM_EMPRESA_ID")
TOKEN_BI   = config["PARAM_TOKEN_BI"]
CERT_PATH  = config["PARAM_BI_CERTI_PATH"]
BI_SERVER  = config["PARAM_BI_SERVER"]
hosts      = config.get("PARAM_IP_CONCENTRADORES", [])

# —————— Prepara log ——————
LOG_PATH = Path(config["PARAM_BASE_DIR"]) / "logs" / "promocao_produto_log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# —————— Funções auxiliares ——————
def send_zabbix_trap(status, message):
    subprocess.run([
        "zabbix_sender",
        "-c", "/etc/zabbix/zabbix_agentd.conf",
        "-s", f"{REDE}-PROXY",
        "-k", "promocao.mysql.conexao",
        "-o", json.dumps({"status": status, "message": message}, ensure_ascii=False)
    ])

def connect_mysql(host, database):
    return mysql.connector.connect(
        host=host,
        user=DB_USER,
        password=DB_PASS,
        database=database,
        connect_timeout=15
    )

def send_to_bi(batch):
    url = f"https://{BI_SERVER}/promocoes/produtos/batch"
    headers = {
        "Authorization": f"Bearer {TOKEN_BI}",
        "Content-Type": "application/json"
    }
    if debug:
        print("\n=== LOTE ENVIADO ===")
        print(json.dumps(batch, indent=2, ensure_ascii=False))
        print("=====================\n")
    try:
        resp = requests.post(url, json=batch, headers=headers, verify=CERT_PATH, timeout=30)
        if resp.status_code == 200:
            print(f"Lote enviado com sucesso: {len(batch)} registros.")
        else:
            print(f"Erro {resp.status_code} ao enviar lote: {resp.text}")
    except Exception as e:
        print(f"Erro ao enviar para API: {e}")

# --- Função principal ---------------------------------------------------
def main():
    with open(LOG_PATH, 'a') as log:
        for host in hosts:
            ts = datetime.now().isoformat(sep=" ")
            log.write(f"{ts} - Conectando ao {host}\n")
            try:
                conn   = connect_mysql(host, "controle")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT nroloja, codigoean, CodGrpMerc "
                    "FROM promocaodesconto_grupo"
                )
                rows   = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"{ts} - Erro ao consultar {host}: {e}\n")
                send_zabbix_trap("erro", f"PROMOCAO - Erro MySQL em {host}")
                continue

            if not rows:
                log.write(f"{ts} - Nenhum dado retornado de {host}\n")
                continue

            send_zabbix_trap("sucesso", f"PROMOCAO - Coleta OK {host}")

            batch_size = 500
            batch = []
            for loja, ean, codgrp in rows:
                batch.append({
                    "empresa_id":  EMPRESA_ID,
                    "loja_codigo": loja,
                    "codigoean":   str(ean),
                    "CodGrpMerc":  str(codgrp)
                })
                if len(batch) >= batch_size:
                    send_to_bi(batch)
                    batch = []
            if batch:
                send_to_bi(batch)

if __name__ == "__main__":
    main()
