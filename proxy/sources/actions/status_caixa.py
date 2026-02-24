# actions/status_caixa.py
"""
Ação local que replica o ConnectAriusServerCAIXA.sh:
- consulta operador_id nos concentradores PostgreSQL
- envia via zabbix_sender para hosts PDV
"""
from __future__ import annotations

import fcntl
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from utils import GREEN, RED, YELLOW, NC


LOCK_FILE = "/run/lock/ConnectAriusServerCAIXA.lock"
MAX_AGE_SECONDS = 60 * 60
ZABBIX_CONFIG = "/etc/zabbix/zabbix_agentd.conf"
ZABBIX_KEY = "pdv.neo.operador_id"

QUERY = """
SELECT l.codigo AS codigo_loja,
       p.codigo AS codigo_pdv,
       b.operadorid
FROM pdvvalor b
JOIN pdv p   ON p.id = b.pdvid
JOIN loja l  ON l.id = p.lojaid
WHERE b.tipo = 5
  AND (b.pdvid, b.coo) IN (
    SELECT a.pdvid, MAX(a.coo)
    FROM pdvvalor a
    WHERE a.tipo = 5
    GROUP BY a.pdvid
  )
ORDER BY l.codigo, p.codigo;
"""


def _acquire_lock(logger: logging.Logger) -> tuple[Path, object] | None:
    lock_path = Path(LOCK_FILE)
    if lock_path.exists():
        try:
            age = int(time.time()) - int(lock_path.stat().st_mtime)
            if age > MAX_AGE_SECONDS:
                logger.warning(
                    f"{YELLOW}[LOCK] Lock antigo detectado (>{MAX_AGE_SECONDS}s). Removendo: {lock_path}{NC}"
                )
                lock_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"{YELLOW}[LOCK] Falha ao avaliar lock: {exc}{NC}")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.error(f"{RED}Outra instância de status_caixa já está em execução. Abortando.{NC}")
        lock_file.close()
        return None

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(f"{os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lock_file.flush()
    return lock_path, lock_file


def _get_cmd_path(cmd: str, fallback: str) -> str:
    return shutil.which(cmd) or fallback


def run_local(config: dict, logger: logging.Logger, args):
    lock_info = _acquire_lock(logger)
    if not lock_info:
        return
    _, lock_file = lock_info

    try:
        remote_hosts = config.get("PARAM_IP_CONCENTRADORES") or []
        rede = config.get("PARAM_REDE")
        db_user = config.get("DB_PG_USER") or config.get("DB_USER")
        db_pass = config.get("DB_PG_PASS") or config.get("DB_PASS")
        db_name = config.get("DB_PG_DB")
        db_port = str(config.get("DB_PG_PORT", 5432))

        if not remote_hosts:
            logger.error("PARAM_IP_CONCENTRADORES não configurado.")
            return
        if not rede:
            logger.error("PARAM_REDE não configurado.")
            return
        if not db_user or not db_pass or not db_name:
            logger.error("Credenciais do PostgreSQL ausentes (DB_PG_USER/DB_PG_PASS/DB_PG_DB).")
            return

        psql_bin = _get_cmd_path("psql", "/usr/bin/psql")
        sender_bin = _get_cmd_path("zabbix_sender", "/usr/bin/zabbix_sender")
        logger.info(f"Usando psql em: {psql_bin}")
        logger.info(f"Usando zabbix_sender em: {sender_bin}")

        for host in remote_hosts:
            logger.info(f"Conectando ao host remoto: {host}")
            env = os.environ.copy()
            env["PGPASSWORD"] = db_pass

            cmd = [
                psql_bin,
                "-h", host,
                "-U", db_user,
                "-d", db_name,
                "-p", db_port,
                "-t", "-A", "-F", "|",
                "-c", QUERY,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)

            if result.returncode != 0:
                err_out = result.stderr.strip() or result.stdout.strip()
                logger.error(f"{RED}Erro ao consultar {host}:{NC} {err_out}")
                continue

            output = result.stdout.strip()
            if not output:
                logger.warning(f"{YELLOW}Sem resultados no host {host}.{NC}")
                continue

            for line in output.splitlines():
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 3:
                    logger.warning(f"{YELLOW}Linha inválida: {line}{NC}")
                    continue

                codigo_loja, codigo_pdv, operadorid = parts[0], parts[1], parts[2]
                if not (codigo_loja.isdigit() and codigo_pdv.isdigit()):
                    logger.warning(
                        f"{YELLOW}Linha inválida: loja='{codigo_loja}' pdv='{codigo_pdv}' op='{operadorid}'{NC}"
                    )
                    continue

                loja_pad = f"{int(codigo_loja):03d}"
                pdv_pad = f"{int(codigo_pdv):03d}"
                host_name = f"{rede}-LOJA{loja_pad}-PDV{pdv_pad}"

                sender_cmd = [
                    sender_bin,
                    "-c", ZABBIX_CONFIG,
                    "-s", host_name,
                    "-k", ZABBIX_KEY,
                    "-o", operadorid,
                ]
                if args.debug:
                    sender_cmd.append("-vv")

                sender_res = subprocess.run(sender_cmd, capture_output=True, text=True)
                if sender_res.returncode == 0:
                    logger.info(
                        f"{GREEN}Enviado com sucesso para {host_name}: operador_id={operadorid}{NC}"
                    )
                else:
                    err_out = sender_res.stderr.strip() or sender_res.stdout.strip()
                    logger.error(
                        f"{RED}Erro ao enviar para {host_name}: operador_id={operadorid}{NC}"
                    )
                    if err_out:
                        logger.error(err_out)
    finally:
        lock_file.close()
