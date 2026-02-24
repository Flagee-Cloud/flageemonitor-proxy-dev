#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import psutil
import argparse
import json
import mysql.connector
import requests
from datetime import datetime

def already_running():
    """
    Retorna True se já existir outra instância Python rodando exatamente este script.
    """
    me_pid    = os.getpid()
    me_script = str(Path(__file__).resolve())
    me_python = sys.executable

    for proc in psutil.process_iter(['pid','exe','cmdline']):
        try:
            pid  = proc.info['pid']
            if pid == me_pid:
                continue
            exe  = proc.info.get('exe')     or ''
            cmd  = proc.info.get('cmdline') or []
            # Só considera processos Python com mesmo executável e mesmo script
            if exe == me_python and len(cmd) >= 2:
                script_path = str(Path(cmd[1]).resolve())
                if script_path == me_script:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

if already_running():
    print("Script já está em execução em outro processo.")
    sys.exit(1)

# ————————————————————————————————————————————————————————————
# Parser de argumentos para debug e datas
parser = argparse.ArgumentParser(description="Sincroniza cupons detalhados com o BI")
parser.add_argument("--dtini", help="Data inicial (YYYY-MM-DD HH:MM:SS)")
parser.add_argument("--dtfim", help="Data final (YYYY-MM-DD HH:MM:SS)")
parser.add_argument("--debug", "-d", action="store_true", help="Modo depuração")
args = parser.parse_args()

# ————————————————————————————————————————————————————————————
# Carrega configurações
with open("/ariusmonitor/config_bot.json") as f:
    config = json.load(f)

debug = args.debug
DB_USER = config["DB_USER"]
DB_PASS = config["DB_PASS"]
TOKEN_BI = config["PARAM_TOKEN_BI"]
REDE     = config["PARAM_REDE"]
CERT_PATH    = config["PARAM_BI_CERTI_PATH"]
BI_SERVER    = config["PARAM_BI_SERVER"]
hosts        = config.get("PARAM_IP_CONCENTRADORES", [])

# Prepara diretório e arquivo de log
LOG_PATH = Path(config["PARAM_BASE_DIR"]) / "logs" / "cupom_detalhe_log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Monta base da query SQL
SQL_BASE = """
SELECT DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV,
       tipooperacao, total, FlagInicupom, FlagFimCupom
FROM cupom
WHERE 1=1
"""
# Ajusta a query conforme parâmetros
if args.dtini and args.dtfim:
    SQL_QUERY = SQL_BASE + f" AND HoraMinSeg BETWEEN '{args.dtini}' AND '{args.dtfim}'"
elif args.dtini:
    SQL_QUERY = SQL_BASE + (
        f" AND HoraMinSeg >= '{args.dtini}'"
        " AND HoraMinSeg <= DATE_SUB(NOW(), INTERVAL 1 HOUR)"
    )
else:
    SQL_QUERY = SQL_BASE + (
        " AND DataProc >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        " AND DataProc <= DATE_SUB(NOW(), INTERVAL 1 DAY)"
    )

# ————————————————————————————————————————————————————————————
def connect_mysql(host, database):
    """Tenta conectar ao MySQL e retorna conexão ou exceção."""
    return mysql.connector.connect(
        host=host,
        user=DB_USER,
        password=DB_PASS,
        database=database,
        connect_timeout=15
    )

def send_to_bi(batch):
    """Envia lote de registros para o BI, respeitando modo debug."""
    url = f"https://{BI_SERVER}/cupons/detalhes"
    headers = {
        "Authorization": f"Bearer {TOKEN_BI}",
        "Content-Type": "application/json"
    }
    if debug:
        print("\n=== LOTE ENVIADO ===")
        print(json.dumps(batch, indent=2, ensure_ascii=False))
        print("=====================\n")
    try:
        r = requests.post(url, json=batch, headers=headers, verify=CERT_PATH, timeout=30)
        if r.status_code == 200:
            print(f"Lote enviado com sucesso: {len(batch)} registros.")
        else:
            print(f"Erro {r.status_code} ao enviar lote: {r.text}")
    except Exception as e:
        print(f"Erro ao enviar para API: {e}")

def main():
    with open(LOG_PATH, 'a') as log:
        for host in hosts:
            log.write(f"{datetime.now()} - Conectando ao {host}\n")
            try:
                conn   = connect_mysql(host, "retag")
                cursor = conn.cursor()
                cursor.execute(SQL_QUERY)
                rows   = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"{datetime.now()} - Erro no host {host}: {e}\n")
                continue

            if not rows:
                log.write(f"{datetime.now()} - Nenhum dado retornado de {host}\n")
                continue

            batch      = []
            batch_size = 500
            for row in rows:
                try:
                    item = {
                        "rede":       REDE,
                        "DataProc":   row[0].isoformat(),
                        "nroloja":    row[1],
                        "NroCupom":   row[2],
                        "Pdv":        row[3],
                        "HoraMinSeg": row[4].isoformat() if row[4] else None,
                        "NroItens":   row[5],
                        "FlagEstorno":row[6],
                        "LV":         row[7],
                        "tipooperacao": row[8],
                        "total":      float(row[9]),
                        "FlagInicupom": row[10],
                        "FlagFimCupom": row[11],
                    }
                    batch.append(item)
                    if len(batch) >= batch_size:
                        send_to_bi(batch)
                        batch = []
                except Exception as e:
                    log.write(f"{datetime.now()} - Erro ao processar item: {e}\n")
            if batch:
                send_to_bi(batch)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erro fatal no script: {e}")
        sys.exit(1)
