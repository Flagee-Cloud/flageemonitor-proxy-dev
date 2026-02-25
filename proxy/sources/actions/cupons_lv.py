# actions/cupons_lv.py
"""
Ação local para coleta de cupons LV e envio ao BI.
Baseada no script standalone Cupons_LV.py.
"""
import json
import subprocess
import requests
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, time
from pathlib import Path
import multiprocessing as mp
import logging


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
        "Authorization": f"Bearer {config['PARAM_TOKEN_BI']}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(
            url,
            headers=headers,
            json=batch,
            timeout=30,
            verify=config["PARAM_BI_CERTI_PATH"]
        )
        if r.status_code == 200:
            print(f"Lote enviado: {len(batch)} registros.")
        else:
            print(f"Erro {r.status_code} ao enviar lote: {r.text}")
    except Exception as e:
        print(f"Falha ao enviar lote: {e}")


def enviar_lote(batch, config, logger: logging.Logger):
    """Wrapper para enviar lote em processo separado com timeout de 90s."""
    proc = mp.Process(target=enviar_lote_em_subprocesso, args=(batch, config))
    proc.start()
    proc.join(timeout=90)
    if proc.is_alive():
        proc.terminate()
        logger.warning("Subprocesso de envio finalizado por timeout.")


def build_date_filter(args):
    if not args.dtini and not args.dtfim:
        return "HoraMinSeg >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)"
    if args.dtini and not args.dtfim:
        return f"HoraMinSeg >= '{args.dtini}'"
    return f"HoraMinSeg BETWEEN '{args.dtini}' AND '{args.dtfim}'"


def run_local(config: dict, logger: logging.Logger, args):
    base_dir = Path(config.get("PARAM_BASE_DIR", "/ariusmonitor"))
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cupons_lv_api_log.txt"

    if logger.hasHandlers():
        # logger already configured by main; keep it but ensure level honors debug flag
        logger.setLevel(logging.DEBUG if getattr(args, "debug", False) else logging.INFO)

    date_filter = build_date_filter(args)
    sql_query = f"""
        SELECT
          DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV, tipooperacao
        FROM cupom
        WHERE LV IN (0,1)
          AND tipooperacao IN (1,2,4,8)
          AND {date_filter}
    """

    for db_host in config.get("PARAM_IP_CONCENTRADORES", []):
        ts = datetime.now().isoformat()
        logger.info(f"{ts} - Coletando cupons do concentrador {db_host}")

        conn = connect_mysql(db_host, config["DB_USER"], config["DB_PASS"], "retag")
        if isinstance(conn, str):
            logger.error(f"Erro conexão {db_host}: {conn}")
            send_zabbix_trap("erro", f"Cupons LV - Erro MySQL {db_host}", config)
            continue

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql_query)
            results = cursor.fetchall()
        except Exception as e:
            logger.error(f"Erro consulta {db_host}: {e}")
            send_zabbix_trap("erro", f"Cupons LV - Falha consulta {db_host}", config)
            continue
        finally:
            cursor.close()
            conn.close()

        if not results:
            logger.info(f"Nenhum cupom encontrado em {db_host}.")
            continue

        send_zabbix_trap("sucesso", f"Cupons LV - Dados coletados de {db_host}", config)

        batch_size = 200
        batch = []
        for row in results:
            hora_value = row["HoraMinSeg"]
            hora_str = (
                hora_value.isoformat()
                if isinstance(hora_value, (datetime, date, time))
                else str(hora_value)
            )
            item = {
                "rede": config["PARAM_REDE"],
                "DataProc": row["DataProc"].isoformat(),
                "nroloja": int(row["nroloja"]),
                "NroCupom": str(row["NroCupom"]),
                "Pdv": int(row["Pdv"]),
                "HoraMinSeg": hora_str,
                "NroItens": int(row["NroItens"]),
                "FlagEstorno": int(row["FlagEstorno"]),
                "LV": int(row["LV"]),
                "tipooperacao": int(row["tipooperacao"])
            }
            batch.append(item)
            if len(batch) >= batch_size:
                logger.info(f"Enviando lote de {len(batch)} registros de {db_host}...")
                enviar_lote(batch, config, logger)
                batch.clear()

        if batch:
            logger.info(f"Enviando lote remanescente de {len(batch)} registros de {db_host}...")
            enviar_lote(batch, config, logger)

    logger.info("Processo de cupons LV concluído com sucesso.")
