#!/usr/bin/env python3
import mysql.connector
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path
from decimal import Decimal, InvalidOperation

# Argumentos
parser = argparse.ArgumentParser(description="Sincroniza promoções com o BI")
parser.add_argument("--dtini", help="Data inicial (YYYY-MM-DD)")
parser.add_argument("--dtfim", help="Data final (YYYY-MM-DD)")
parser.add_argument("--debug", "-d", action="store_true", help="Modo de depuração")
args = parser.parse_args()

# Carrega configuração
with open("/ariusmonitor/config_bot.json") as f:
    config = json.load(f)

DB_USER = config["DB_USER"]
DB_PASS = config["DB_PASS"]
TOKEN_BI = config["PARAM_TOKEN_BI"]
REDE = config["PARAM_REDE"]
EMPRESA_ID = config["PARAM_EMPRESA_ID"]
CERT_PATH = config["PARAM_BI_CERTI_PATH"]
LOG_PATH = Path(config["PARAM_BASE_DIR"]) / "logs" / "mercador_promocoes_log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQL Base
SQL_BASE = """
SELECT nroloja, CodPromocao, Descricao, TipoPromocao, CodGrpGatilho, QtdGatilho,
       CodGrpDesc, QtdDesc, PercDesc, DataInicio, DataFim, DataExclusao, Excluido,
       vinculadoMeioPagto, TipoDesconto, ExcluiOferta, nome_campanha,
       VlrDescUnit, VlrFinalUnit, VlrMaxTotal
FROM promocaodesconto
WHERE 1=1
"""

# Ajusta SQL
if args.dtini and args.dtfim:
    SQL_QUERY = SQL_BASE + f" AND DataFim BETWEEN '{args.dtini}' AND '{args.dtfim}'"
elif args.dtini:
    SQL_QUERY = SQL_BASE + f" AND DataFim >= '{args.dtini}'"
else:
    SQL_QUERY = SQL_BASE + " AND DataFim >= NOW()"

def connect_mysql(host, database):
    return mysql.connector.connect(
        host=host,
        user=DB_USER,
        password=DB_PASS,
        database=database,
        connect_timeout=15
    )

def decimal_or_none(val):
    try:
        return float(val) if isinstance(val, (Decimal, float)) else None
    except (InvalidOperation, TypeError):
        return None

def send_to_bi(lote):
    url = f"https://{config['PARAM_BI_SERVER']}/promocoes/batch"
    headers = {
        "Authorization": f"Bearer {TOKEN_BI}",
        "Content-Type": "application/json"
    }

    if args.debug:
        print("\n=== LOTE ENVIADO ===")
        print(json.dumps(lote, indent=2, ensure_ascii=False))
        print("======================\n")

    try:
        response = requests.post(url, json=lote, headers=headers, verify=CERT_PATH, timeout=30)
        if response.status_code == 200:
            print(f"Lote enviado com sucesso: {len(lote)} registros.")
        else:
            print(f"Erro {response.status_code} ao enviar lote: {response.text}")
    except Exception as e:
        print(f"Erro ao enviar para API: {e}")

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
                log.write(f"{datetime.now()} - Nenhum dado retornado de {host}\n")
                continue

            batch_size = 500
            batch = []
            for row in rows:
                item = {
                    "empresa_id": EMPRESA_ID,
                    "loja_codigo": row[0],
                    "CodPromocao": str(row[1]) if row[1] is not None else None,
                    "Descricao": row[2],
                    "TipoPromocao": row[3],
                    "CodGrpGatilho": str(row[4]) if row[4] is not None else None,
                    "QtdGatilho": row[5],
                    "CodGrpDesc": str(row[6]) if row[6] is not None else None,
                    "QtdDesc": row[7],
                    "PercDesc": decimal_or_none(row[8]),
                    "DataInicio": row[9].isoformat() if row[9] else None,
                    "DataFim": row[10].isoformat() if row[10] else None,
                    "DataExclusao": row[11].isoformat() if row[11] else None,
                    "Excluido": row[12],
                    "vinculadoMeioPagto": row[13],
                    "TipoDesconto": row[14],
                    "ExcluiOferta": row[15],
                    "nome_campanha": row[16],
                    "VlrDescUnit": decimal_or_none(row[17]),
                    "VlrFinalUnit": decimal_or_none(row[18]),
                    "VlrMaxTotal": decimal_or_none(row[19])
                }
                batch.append(item)
                if len(batch) >= batch_size:
                    send_to_bi(batch)
                    batch = []
            if batch:
                send_to_bi(batch)

if __name__ == "__main__":
    main()
