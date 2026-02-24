# actions/cupons_detalhes.py
"""
Ação local para sincronizar cupons detalhados com o BI.
Baseada no script standalone CuponsDetalhes.py.
"""
import json
import mysql.connector
import requests
from datetime import datetime
from pathlib import Path
import logging


def connect_mysql(host, user, password, database):
    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        connect_timeout=15
    )


def send_to_bi(batch, config, debug, logger: logging.Logger):
    url = f"https://{config['PARAM_BI_SERVER']}/cupons/detalhes"
    headers = {
        "Authorization": f"Bearer {config['PARAM_TOKEN_BI']}",
        "Content-Type": "application/json"
    }
    if debug:
        logger.debug("Lote enviado (debug): %s", json.dumps(batch, indent=2, ensure_ascii=False))
    try:
        r = requests.post(url, json=batch, headers=headers, verify=config["PARAM_BI_CERTI_PATH"], timeout=30)
        if r.status_code == 200:
            logger.info(f"Lote enviado com sucesso: {len(batch)} registros.")
        else:
            logger.error(f"Erro {r.status_code} ao enviar lote: {r.text}")
    except Exception as e:
        logger.error(f"Erro ao enviar para API: {e}")


def build_sql(args):
    sql_base = """
    SELECT DataProc, nroloja, NroCupom, Pdv, HoraMinSeg, NroItens, FlagEstorno, LV,
           tipooperacao, total, FlagInicupom, FlagFimCupom
    FROM cupom
    WHERE 1=1
    """
    if args.dtini and args.dtfim:
        return sql_base + f" AND HoraMinSeg BETWEEN '{args.dtini}' AND '{args.dtfim}'"
    if args.dtini:
        return sql_base + (
            f" AND HoraMinSeg >= '{args.dtini}'"
            " AND HoraMinSeg <= DATE_SUB(NOW(), INTERVAL 1 HOUR)"
        )
    return sql_base + (
        " AND DataProc >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        " AND DataProc <= DATE_SUB(NOW(), INTERVAL 1 DAY)"
    )


def run_local(config: dict, logger: logging.Logger, args):
    debug = bool(getattr(args, "debug", False))
    hosts = config.get("PARAM_IP_CONCENTRADORES", [])
    log_path = Path(config["PARAM_BASE_DIR"]) / "logs" / "cupom_detalhe_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    sql_query = build_sql(args)

    with open(log_path, "a") as log:
        for host in hosts:
            log.write(f"{datetime.now()} - Conectando ao {host}\n")
            try:
                conn = connect_mysql(host, config["DB_USER"], config["DB_PASS"], "retag")
                cursor = conn.cursor()
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
            except Exception as e:
                log.write(f"{datetime.now()} - Erro no host {host}: {e}\n")
                logger.error(f"Erro no host {host}: {e}")
                continue

            if not rows:
                log.write(f"{datetime.now()} - Nenhum dado retornado de {host}\n")
                logger.info(f"Nenhum dado retornado de {host}")
                continue

            batch = []
            batch_size = 500
            for row in rows:
                try:
                    item = {
                        "rede":        config["PARAM_REDE"],
                        "DataProc":    row[0].isoformat(),
                        "nroloja":     row[1],
                        "NroCupom":    row[2],
                        "Pdv":         row[3],
                        "HoraMinSeg":  row[4].isoformat() if row[4] else None,
                        "NroItens":    row[5],
                        "FlagEstorno": row[6],
                        "LV":          row[7],
                        "tipooperacao": row[8],
                        "total":       float(row[9]),
                        "FlagInicupom": row[10],
                        "FlagFimCupom": row[11],
                    }
                    batch.append(item)
                    if len(batch) >= batch_size:
                        send_to_bi(batch, config, debug, logger)
                        batch = []
                except Exception as e:
                    log.write(f"{datetime.now()} - Erro ao processar item: {e}\n")
                    logger.error(f"Erro ao processar item: {e}")
            if batch:
                send_to_bi(batch, config, debug, logger)

    logger.info("Sincronização de cupons detalhados finalizada.")
