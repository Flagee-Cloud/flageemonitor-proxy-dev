#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import psutil
import json
import subprocess
import requests
import mysql.connector
from mysql.connector import Error
import argparse
from datetime import datetime, date, time
import multiprocessing as mp


def already_running():
    """Retorna True se já existir outra instância Python rodando exatamente este script."""
    me_pid = os.getpid()
    me_script = str(Path(__file__).resolve())
    me_python = sys.executable

    for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
        try:
            if proc.info['pid'] == me_pid:
                continue
            if proc.info.get('exe') == me_python and len(proc.info.get('cmdline') or []) >= 2:
                if str(Path(proc.info['cmdline'][1]).resolve()) == me_script:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


if already_running():
    print("Script já está em execução em outro processo.")
    sys.exit(1)


def load_config(config_file):
    """Carrega configuração JSON de arquivo."""
    with open(config_file, 'r') as f:
        return json.load(f)


def send_zabbix_trap(status, message, config):
    """Envia trap para Zabbix indicando status e mensagem."""
    zbx_sender_server = config.get("PARAM_ZABBIX_SENDER_SERVER", "127.0.0.1")
    zbx_sender_port = str(config.get("PARAM_ZABBIX_SENDER_PORT", "10051"))
    cmd = [
        "zabbix_sender",
        "-z", zbx_sender_server,
        "-p", zbx_sender_port,
        "-s", f"{config['PARAM_REDE']}-PROXY",
        "-k", "concentrador.cupons.lote",
        "-o", f'{{"status":"{status}","message":"{message}"}}'
    ]
    subprocess.run(cmd)


def connect_mysql(host, user, password, database, timeout=60):
    """Tenta conectar ao MySQL."""
    try:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            connect_timeout=timeout
        )
    except Error as e:
        return str(e)


def enviar_lote_em_subprocesso(batch, config):
    """Envia lote via subprocesso para não bloquear execução principal."""
    url = f"https://{config['PARAM_BI_SERVER']}/cupons/detalhes"
    headers = {
        'Authorization': f"Bearer {config['PARAM_TOKEN_BI']}",
        'Content-Type': 'application/json'
    }
    try:
        r = requests.post(url, headers=headers, json=batch,
                          timeout=30, verify=config['PARAM_BI_CERTI_PATH'])
        if r.status_code == 200:
            print(f"Lote enviado: {len(batch)} registros.")
        else:
            print(f"Erro {r.status_code} ao enviar lote: {r.text}")
    except Exception as e:
        print(f"Falha ao enviar lote: {e}")


def enviar_lote(batch, config):
    """Wrapper para enviar lote em processo separado com timeout de 90s."""
    proc = mp.Process(target=enviar_lote_em_subprocesso, args=(batch, config))
    proc.start()
    proc.join(timeout=90)
    if proc.is_alive():
        proc.terminate()
        print("Subprocesso de envio finalizado por timeout.")


def main():
    parser = argparse.ArgumentParser(
        description="Coleta de cupons dos concentradores e envio para API do BI"
    )
    parser.add_argument('dtini', nargs='?', help='Data inicial (YYYY-MM-DD)')
    parser.add_argument('dtfim', nargs='?', help='Data final (YYYY-MM-DD)')
    parser.add_argument('--debug', '-d', action='store_true', help='Modo debug')
    args = parser.parse_args()

    # Carrega configuração
    config = load_config('/ariusmonitor/config_bot.json')
    base_dir = Path(config.get('PARAM_BASE_DIR', '/ariusmonitor'))
    log_dir = base_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'cupons_lv_api_log.txt'

    # Configura logging
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(fh)
    logger.addHandler(sh)

    # Define filtro de datas
    if not args.dtini and not args.dtfim:
        date_filter = 'HoraMinSeg >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)'
    elif args.dtini and not args.dtfim:
        date_filter = f"HoraMinSeg >= '{args.dtini}'"
    else:
        date_filter = f"HoraMinSeg BETWEEN '{args.dtini}' AND '{args.dtfim}'"

    # Query sem filtrar coluna inexistente 'rede'
    sql_query = f"""
        SELECT
          DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao
        FROM cupom
        WHERE LV IN (0,1)
          AND tipooperacao IN (1,2,4,8)
          AND {date_filter}
    """

    # Itera sobre concentradores
    for db_host in config['PARAM_IP_CONCENTRADORES']:
        ts = datetime.now().isoformat()
        logger.info(f"{ts} - Coletando cupons do concentrador {db_host}")

        conn = connect_mysql(db_host, config['DB_USER'], config['DB_PASS'], 'retag')
        if isinstance(conn, str):
            logger.error(f"Erro conexão {db_host}: {conn}")
            send_zabbix_trap('erro', f"Cupons LV - Erro MySQL {db_host}", config)
            continue

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql_query)
            results = cursor.fetchall()
        except Exception as e:
            logger.error(f"Erro consulta {db_host}: {e}")
            send_zabbix_trap('erro', f"Cupons LV - Falha consulta {db_host}", config)
            continue
        finally:
            cursor.close()
            conn.close()

        if not results:
            logger.info(f"Nenhum cupom encontrado em {db_host}.")
            continue

        send_zabbix_trap('sucesso', f"Cupons LV - Dados coletados de {db_host}", config)

        # Envia em lotes para API
        batch_size = 200
        batch = []
        for row in results:
            # Conversão de objetos datetime/time para string
            hora_str = row['HoraMinSeg'].isoformat() if isinstance(row['HoraMinSeg'], (datetime, date, time)) else str(row['HoraMinSeg'])
            item = {
                'rede': config['PARAM_REDE'],
                'DataProc': row['DataProc'].isoformat(),
                'nroloja': int(row['nroloja']),
                'NroCupom': str(row['NroCupom']),
                'Pdv': int(row['Pdv']),
                'HoraMinSeg': hora_str,
                'NroItens': int(row['NroItens']),
                'FlagEstorno': int(row['FlagEstorno']),
                'LV': int(row['LV']),
                'tipooperacao': int(row['tipooperacao'])
            }
            batch.append(item)
            if len(batch) >= batch_size:
                logger.info(f"Enviando lote de {len(batch)} registros de {db_host}...")
                enviar_lote(batch, config)
                batch.clear()

        if batch:
            logger.info(f"Enviando lote remanescente de {len(batch)} registros de {db_host}...")
            enviar_lote(batch, config)

    logger.info("Processo concluído com sucesso.")


if __name__ == '__main__':
    main()
