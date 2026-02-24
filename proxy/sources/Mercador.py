#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import json
import psutil
import requests
import subprocess
import mysql.connector
from datetime import datetime
from pathlib import Path
import argparse

# —————— Função para checar outra instância em execução ——————
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

# —————— Parser de argumentos ——————
parser = argparse.ArgumentParser(description="Sincroniza dados do Mercador com o BI")
parser.add_argument("--dtini", help="Data inicial (YYYY-MM-DD HH:MM:SS)")
parser.add_argument("--dtfim", help="Data final (YYYY-MM-DD HH:MM:SS)")
parser.add_argument("--debug", "-d", action="store_true", help="Modo depuração")
args = parser.parse_args()

# —————— Carrega configuração ——————
with open("/ariusmonitor/config_bot.json") as f:
    config = json.load(f)

REDE       = config["PARAM_REDE"]
EMPRESA_ID = config["PARAM_EMPRESA_ID"]
TOKEN_BI   = config["PARAM_TOKEN_BI"]
CERT_PATH  = config["PARAM_BI_CERTI_PATH"]
BASE_DIR   = Path(config["PARAM_BASE_DIR"])
LOG_PATH   = BASE_DIR / "logs" / "mercador_log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# —————— Monta SQL conforme parâmetros ——————
SQL_BASE = (
    "SELECT loja_codigo, codigoean, codigoint, depto, valor, "
    "descricao_completa, descricao, dataalt, dthr_alt, validade, "
    "desconto, estoque, estoque_atual, Grupo "
    "FROM mercador WHERE 1=1"
)

if args.dtini and args.dtfim:
    SQL_QUERY = f"{SQL_BASE} AND dthr_alt BETWEEN '{args.dtini}' AND '{args.dtfim}'"
elif args.dtini:
    SQL_QUERY = f"{SQL_BASE} AND dthr_alt >= '{args.dtini}'"
else:
    SQL_QUERY = f"{SQL_BASE} AND dthr_alt >= NOW()"

# —————— Funções auxiliares ——————
def send_zabbix_trap(status, message):
    subprocess.run([
        "zabbix_sender",
        "-c", "/etc/zabbix/zabbix_agentd.conf",
        "-s", f"{REDE}-PROXY",
        "-k", "mercador.mysql.conexao",
        "-o", json.dumps({"status": status, "message": message}, ensure_ascii=False)
    ])

def connect_mysql(host, database):
    return mysql.connector.connect(
        host=host,
        user=config["DB_USER"],
        password=config["DB_PASS"],
        database=database,
        connect_timeout=15
    )

def build_payload(row):
    return {
        "empresa_id":        EMPRESA_ID,
        "loja_codigo":       row[0],
        "codigoean":         row[1],
        "codigoint":         str(row[2]) if row[2] is not None else None,
        "depto":             row[3],
        "valor":             float(row[4]) if row[4] is not None else None,
        "descricao_completa":row[5],
        "descricao":         row[6],
        "dataalt":           row[7].isoformat() if row[7] else None,
        "dthr_alt":          row[8].isoformat() if row[8] else None,
        "validade":          row[9].isoformat() if row[9] else None,
        "desconto":          float(row[10]) if row[10] is not None else None,
        "estoque":           row[11],
        "estoque_atual":     row[12],
        "Grupo":             row[13]
    }

def send_to_bi(batch):
    url = f"https://{config['PARAM_BI_SERVER']}/mercador/batch"
    headers = {
        "Authorization": f"Bearer {TOKEN_BI}",
        "Content-Type":  "application/json"
    }
    if args.debug:
        print("\n=== LOTE ENVIADO ===")
        print(json.dumps(batch, indent=2, ensure_ascii=False))
        print("====================\n")
    try:
        resp = requests.post(url, json=batch, headers=headers, verify=CERT_PATH, timeout=30)
        if resp.status_code == 200:
            print(f"Lote enviado: {len(batch)} registros.")
        else:
            print(f"Erro {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Falha no envio: {e}")

# —————— Função principal ——————
def main():
    with open(LOG_PATH, "a") as log:
        for host in config["PARAM_IP_CONCENTRADORES"]:
            ts = datetime.now().isoformat(sep=" ")
            log.write(f"{ts} - Conectando a {host}\n")
            try:
                conn   = connect_mysql(host, "retag")
                cursor = conn.cursor()
                cursor.execute(SQL_QUERY)
                rows   = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"{ts} - Erro em {host}: {e}\n")
                send_zabbix_trap("erro", f"MERCADOR - Erro MySQL em {host}")
                continue

            if not rows:
                log.write(f"{ts} - Sem resultados em {host}\n")
                continue

            send_zabbix_trap("sucesso", f"MERCADOR - Conectado em {host}")

            batch = []
            for row in rows:
                batch.append(build_payload(row))
                if len(batch) >= 1000:
                    send_to_bi(batch)
                    batch = []
            if batch:
                send_to_bi(batch)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)
