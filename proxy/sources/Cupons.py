#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import psutil

def already_running():
    """Retorna True se já existir outra instância Python rodando exatamente este script."""
    me_pid    = os.getpid()
    me_script = str(Path(__file__).resolve())
    me_python = sys.executable

    for proc in psutil.process_iter(['pid','exe','cmdline']):
        try:
            pid = proc.info['pid']
            if pid == me_pid:
                continue
            exe  = proc.info.get('exe')     or ''
            cmd  = proc.info.get('cmdline') or []
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

# —–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

import json
import mysql.connector
import subprocess
import requests
import argparse
from datetime import datetime

# --- Funções auxiliares --------------------------------------------------

def load_config(config_file):
    """Carrega configuração JSON de arquivo."""
    with open(config_file, 'r') as f:
        return json.load(f)

def send_zabbix_trap(status, message, config):
    """Envia trap para Zabbix indicando status e mensagem."""
    conf_path = Path("/etc/zabbix/zabbix_agentd.conf")
    cmd = [
        "zabbix_sender",
        "-s", f"{config['PARAM_REDE']}-PROXY",
        "-k", "concentrador.mysql.conexao",
        "-o", f'{{"status":"{status}", "message":"{message}"}}'
    ]
    if conf_path.exists():
        cmd[1:1] = ["-c", str(conf_path)]
    else:
        cmd[1:1] = ["-z", config.get("PARAM_ZABBIX_SERVER","127.0.0.1"), "-p", "10051"]
    subprocess.run(cmd)

def connect_mysql(host, user, password, database):
    """Tenta conectar ao MySQL com timeout de 60s."""
    try:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            connect_timeout=60
        )
    except mysql.connector.Error as e:
        return str(e)

def enviar_lote(batch, config, debug=False):
    url    = f"https://{config['PARAM_BI_SERVER']}/cupons/batch"
    token  = config['PARAM_TOKEN_BI']
    headers = {
        'Authorization': f"Bearer {token}",
        'Content-Type':  'application/json'
    }
    try:
        r = requests.post(
            url, headers=headers, json=batch,
            timeout=90, verify=config['PARAM_BI_CERTI_PATH']
        )
        if r.status_code == 200:
            print(f"Lote enviado: {len(batch)} registros.")
        else:
            print(f"Erro {r.status_code} ao enviar lote: {r.text}")
    except requests.Timeout:
        print("Envio de lote excedeu o timeout de 90s.")
    except Exception as e:
        print(f"Falha ao enviar lote: {e}")

# --- Função principal ----------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Envio de cupons NFC-e para API do BI"
    )
    parser.add_argument("dtini", nargs="?", help="Data inicial (YYYY-MM-DD)")
    parser.add_argument("dtfim", nargs="?", help="Data final (YYYY-MM-DD)")
    parser.add_argument("--debug", "-d", action="store_true", help="Modo debug")
    args = parser.parse_args()

    config   = load_config("/ariusmonitor/config_bot.json")
    log_dir  = Path(config['PARAM_BASE_DIR']) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'cupons_log.txt'

    # Se for a rede ESTRELA, aplica filtro de lojas específicas
    filtro_nroloja = ""
    if config.get('PARAM_REDE') == 'ESTRELA':
        filtro_nroloja = " AND nroloja IN (100,101,102,103,104,105,106)"

    # Monta a query conforme args...
    if not args.dtini and not args.dtfim:
        sql_query = f"""
            SELECT nroloja, dthr_emit_nfe, Pdv, NroCupom, estornado,
                   chave_nfe, vICMS, vICMS_ST, vPIS, vPIS_ST,
                   vCOFINS, vCOFINS_ST, vFCP, vFCP_ST, LV, Status
            FROM nfce
            WHERE dthr_emit_nfe >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
              AND chave_nfe != ''{filtro_nroloja};
        """
    elif args.dtini and not args.dtfim:
        sql_query = f"""
            SELECT nroloja, dthr_emit_nfe, Pdv, NroCupom, estornado,
                   chave_nfe, vICMS, vICMS_ST, vPIS, vPIS_ST,
                   vCOFINS, vCOFINS_ST, vFCP, vFCP_ST, LV, Status
            FROM nfce
            WHERE dthr_emit_nfe >= '{args.dtini}'
              AND chave_nfe != ''{filtro_nroloja};
        """
    else:
        sql_query = f"""
            SELECT nroloja, dthr_emit_nfe, Pdv, NroCupom, estornado,
                   chave_nfe, vICMS, vICMS_ST, vPIS, vPIS_ST,
                   vCOFINS, vCOFINS_ST, vFCP, vFCP_ST, LV, Status
            FROM nfce
            WHERE dthr_emit_nfe BETWEEN '{args.dtini}' AND '{args.dtfim}'
              AND chave_nfe != ''{filtro_nroloja};
        """


    with open(log_file, 'a') as log:
        for db_host in config['PARAM_IP_CONCENTRADORES']:
            ts = datetime.now().isoformat()
            msg = f"{ts} - Conectando ao IP {db_host}"
            print(msg)
            log.write(msg + "\n")

            conn = connect_mysql(
                db_host,
                config['DB_USER'],
                config['DB_PASS'],
                "retag"
            )
            if isinstance(conn, str):
                ts = datetime.now().isoformat()
                err = f"{ts} - Erro conexão {db_host}: {conn}"
                print(err)
                log.write(err + "\n")
                send_zabbix_trap("erro", f"NFCE - Erro MySQL em {db_host}", config)
                continue

            try:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                results = cursor.fetchall()
            except Exception as e:
                ts = datetime.now().isoformat()
                err = f"{ts} - Erro consulta em {db_host}: {e}"
                print(err)
                log.write(err + "\n")
                send_zabbix_trap("erro", f"NFCE - Falha consulta {db_host}", config)
                continue
            finally:
                cursor.close()
                conn.close()

            if not results:
                ts = datetime.now().isoformat()
                nres = f"{ts} - Nenhum resultado em {db_host}"
                print(nres)
                log.write(nres + "\n")
                continue

            send_zabbix_trap("sucesso", f"NFCE - Conectado ao MySQL {db_host}", config)

            batch_size = 200
            batch = []
            for row in results:
                modelo = row[5][20:22] if len(row[5]) >= 22 else "0"
                item = {
                    "rede":       config['PARAM_REDE'],
                    "nroloja":    row[0],
                    "DataProc":   row[1].isoformat(),
                    "Pdv":        int(row[2]),
                    "Chave":      row[5],
                    "modelo":     int(modelo),
                    "emServidor": 1,
                    "nCupom":     row[3],
                    "vICMS":      float(row[6]),
                    "vICMS_ST":   float(row[7]),
                    "vPIS":       float(row[8]),
                    "vPIS_ST":    float(row[9]),
                    "vCOFINS":    float(row[10]),
                    "vCOFINS_ST": float(row[11]),
                    "vFCP":       float(row[12]),
                    "vFCP_ST":    float(row[13]),
                    "LV":         row[14],
                    "estornado":  int(row[4]),
                    "dEmi":       row[1].isoformat(),
                    "Status":     str(row[15]) if row[15] is not None else ""
                }
                batch.append(item)

                if len(batch) >= batch_size:
                    ts = datetime.now().isoformat()
                    msg = f"{ts} - Enviado lote de {len(batch)} registros para {db_host}"
                    print(msg)
                    log.write(msg + "\n")
                    enviar_lote(batch, config, debug=args.debug)
                    batch = []

            # Envia o lote remanescente
            if batch:
                ts = datetime.now().isoformat()
                msg = f"{ts} - Enviado lote de {len(batch)} registros para {db_host}"
                print(msg)
                log.write(msg + "\n")
                enviar_lote(batch, config, debug=args.debug)

if __name__ == "__main__":
    main()
