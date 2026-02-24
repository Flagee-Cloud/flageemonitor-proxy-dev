#!/usr/bin/env python3

import logging
from logging.handlers import RotatingFileHandler

# Códigos ANSI de cores para logs e outputs
GREEN   = '\033[0;32m'
RED     = '\033[0;31m'
YELLOW  = '\033[0;33m'
BLUE    = '\033[0;34m'
NC      = '\033[0m'  # No Color / reset

# --- ALTERAÇÃO 1: A função agora aceita o argumento 'debug' ---
def setup_logging(config: dict, debug: bool = False) -> logging.Logger:
    """
    Configura o logger global com rotação de arquivos e console.
    """
    fmt = logging.Formatter(
        '%(asctime)s [%(threadName)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger()

    # --- ALTERAÇÃO 2: O nível de log é definido dinamicamente ---
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Log em modo DEBUG ativado.")
    else:
        logger.setLevel(logging.INFO)

    # Silencia os logs internos do paramiko para evitar poluição
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    # --- O resto do arquivo permanece igual ---

    # Evita adicionar handlers duplicados se a função for chamada mais de uma vez
    if not logger.handlers:
        # Console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

        # RotatingFileHandler para log geral
        general_log = config['logfiles']['general']
        max_bytes = config.get('log_rotation', {}).get('max_bytes', 10 * 1024 * 1024)
        backup_count = config.get('log_rotation', {}).get('backup_count', 5)

        file_handler = RotatingFileHandler(
            filename=general_log,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger