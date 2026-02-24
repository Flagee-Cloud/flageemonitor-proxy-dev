import os
import json
import mysql.connector
from mysql.connector import Error
import csv

# Carregar configurações do arquivo JSON
with open('config_bot.json', 'r') as config_file:
    config = json.load(config_file)

# Acessar as configurações
PARAM_EMPRESA_ID = config["PARAM_EMPRESA_ID"]
DB_CONFIG_REMOTE = {
    "user": config["DB_USER"],
    "password": config["DB_PASS"],
    "host": config["PARAM_IP_CONCENTRADORES"][0],  # Exemplo: 1º concentrador
    "database": "retag"
}
DB_CONFIG_BI = {
    "user": config["DB_USER_BI"],
    "password": config["DB_PASS_BI"],
    "host": config["DB_HOST_BI"],
    "database": config["DB_NAME_BI"]
}
BATCH_SIZE = 100000
CONCENTRADORES = config["PARAM_IP_CONCENTRADORES"]

LOG_DIR = "logs"
TMP_DIR = "/tmp/mercador_grupos_csv"

# Garantir que os diretórios existem
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "script_log_mercador_grupos.txt")


def log_message(message):
    with open(LOG_FILE, "a") as log:
        log.write(f"{message}\n")
    print(message)


def connect_to_database(config):
    try:
        return mysql.connector.connect(**config, allow_local_infile=True)
    except Error as e:
        log_message(f"Erro ao conectar ao banco de dados: {e}")
        return None


def export_to_csv(cursor, query, csv_file):
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            return False

        with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
            writer.writerows(rows)
        return True
    except Error as e:
        log_message(f"Erro ao exportar para CSV: {e}")
        return False


def load_data_to_bi(connection, csv_file):
    try:
        cursor = connection.cursor()
        cursor.execute("SET SESSION sql_mode = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';")
        query = f"""
        LOAD DATA LOCAL INFILE '{csv_file}' INTO TABLE mercador_intermediaria
        FIELDS TERMINATED BY '\t'
        OPTIONALLY ENCLOSED BY '"'
        LINES TERMINATED BY '\n'
        (empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo);
        """
        cursor.execute(query)
        connection.commit()
        cursor.close()
        return True
    except Error as e:
        log_message(f"Erro ao carregar dados para o banco BI: {e}")
        return False


def insert_data_to_final_table(connection):
    try:
        cursor = connection.cursor()
        query = """
        INSERT INTO mercador (empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo
)
        SELECT empresa_id, loja_codigo, codigoean, codigoint, depto, valor, descricao_completa, descricao, dataalt, dthr_alt, validade, desconto, unidade, Grupo
        FROM mercador_intermediaria
        ON DUPLICATE KEY UPDATE
        depto=VALUES(depto), valor=VALUES(valor), descricao_completa=VALUES(descricao_completa), descricao=VALUES(descricao),
        dataalt=VALUES(dataalt), dthr_alt=VALUES(dthr_alt), desconto=VALUES(desconto), unidade=VALUES(unidade), Grupo=VALUES(Grupo);
        """
        cursor.execute(query)
        connection.commit()
        cursor.close()
        return True
    except Error as e:
        log_message(f"Erro ao inserir dados na tabela final: {e}")
        return False


def process_concentrador(db_host):
    log_message(f"Conectando ao IP {db_host}")
    offset = 0

    connection_remote = connect_to_database({**DB_CONFIG_REMOTE, "host": db_host})
    connection_bi = connect_to_database(DB_CONFIG_BI)

    if not connection_remote or not connection_bi:
        return

    cursor_remote = connection_remote.cursor()

    while True:
        csv_file = os.path.join(TMP_DIR, f"mercador_{db_host}_{offset}.csv")
        query = f"""
        SELECT '{PARAM_EMPRESA_ID}' AS empresa_id, nroloja AS loja_codigo, codigoean, codigoint,
               IF(depto = '' OR depto IS NULL, 0, depto) AS depto,
               valor, LEFT(descricao_completa, 80) AS descricao_completa,
               LEFT(descricao, 30) AS descricao, LEFT(dataalt, 6) AS dataalt,
               dthr_alt, LEFT(validade, 3) AS validade, desconto, unidade, Grupo
        FROM mercador
        LIMIT {BATCH_SIZE} OFFSET {offset};
        """
        if not export_to_csv(cursor_remote, query, csv_file):
            log_message(f"Erro: Arquivo CSV vazio ou não gerado: {csv_file}")
            break

        if not load_data_to_bi(connection_bi, csv_file):
            break

        if not insert_data_to_final_table(connection_bi):
            break

        log_message(f"Arquivo CSV processado: {csv_file}")
        offset += BATCH_SIZE

    cursor_remote.close()
    connection_remote.close()
    connection_bi.close()


def main():
    for db_host in CONCENTRADORES:
        process_concentrador(db_host)


if __name__ == "__main__":
    main()