# pdv_asset_manager.py
import os
import logging
import requests
import hashlib
import shutil
from utils import GREEN, RED, NC

# This dictionary will be populated by the download function and used by other modules.
LOCAL_CHECKSUMS = {}

def _calculate_local_checksum(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return None

def download_assets_for_action(action: str, config: dict) -> bool:
    """
    Verifica a ação e baixa os arquivos necessários, calculando e populando
    o dicionário global LOCAL_CHECKSUMS.
    """
    logger = logging.getLogger()
    repo_url = config.get("PARAM_REPO_URL", "https://ariusmonitor-repo.flagee.cloud")
    local_dir = config.get("PARAM_LOCAL_ASSET_DIR", "/ariusmonitor/host-linux")
    source_dir = config.get("PARAM_LOCAL_REPO_DIR")
    if not source_dir and os.path.isdir("/ariusmonitor/repositorio"):
        source_dir = "/ariusmonitor/repositorio"
    
    files_to_download = []
    if action == "pdv_install":
        files_to_download.append("ariusmonitor.tar.gz")
    if action in ["pdv_install", "pdv_update_config"]:
        files_to_download.extend([
            "geral.conf", "MonitoraSATc", "MonitoraSATc64",
            "MonitoraSAT.sh", "MonitoraImpressora", "libs.tar.gz"
        ])
    
    if not files_to_download:
        return True
        
    logger.info(f"Preparando assets para a ação '{action}'...")
    try:
        os.makedirs(local_dir, exist_ok=True)
        if source_dir:
            logger.info(f"Usando assets locais de '{source_dir}' como fonte primária.")
        for filename in set(files_to_download):
            local_path = os.path.join(local_dir, filename)
            logger.info(f"Baixando/Verificando asset: {filename}...")
            source_path = os.path.join(source_dir, filename) if source_dir else None
            if source_path and os.path.exists(source_path):
                if os.path.abspath(source_path) != os.path.abspath(local_path):
                    source_checksum = _calculate_local_checksum(source_path)
                    local_checksum = _calculate_local_checksum(local_path) if os.path.exists(local_path) else None
                    if local_checksum != source_checksum:
                        shutil.copy2(source_path, local_path)
            else:
                # Simple check to avoid re-downloading if file exists. A more robust check
                # could involve checking a manifest file from the repo first.
                if not os.path.exists(local_path):
                    response = requests.get(f"{repo_url}/{filename}", timeout=120)
                    response.raise_for_status()
                    with open(local_path, 'wb') as f:
                        f.write(response.content)

            # Always calculate and store the checksum of the local file
            LOCAL_CHECKSUMS[filename] = _calculate_local_checksum(local_path)
        
        logger.info(f"{GREEN}Todos os assets necessários estão prontos.{NC}")
        return True
    except Exception as e:
        logger.error(f"{RED}Falha crítica ao baixar assets. Erro: {e}{NC}")
        return False
