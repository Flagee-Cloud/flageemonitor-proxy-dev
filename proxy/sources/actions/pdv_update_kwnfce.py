# actions/pdv_update_kwnfce.py

import os
import logging
import tempfile

from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC

ACTION_NAME = "pdv_update_kwnfce"
ACTION_VERSION = "2025-11-25.v1"

def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Action: pdv_update_kwnfce

    Objetivo:
      - Garantir que /posnet/kwnfce.conf exista.
      - Garantir que ele contenha exatamente: HORA_Z=0
      - Garantir chown root:root e chmod 644.
    """

    host_name = host.get("host", "UNKNOWN")
    host_prefix = f"[{host_name}]"

    logger.info(
        f"{host_prefix} Iniciando ação '{ACTION_NAME}' "
        f"(versão {ACTION_VERSION})..."
    )

    needs_sudo = session.user != "root"
    remote_dir = "/posnet"
    remote_conf = f"{remote_dir}/kwnfce.conf"

    # --- 1) Garante o diretório /posnet ---
    mkdir_cmd = f"mkdir -p '{remote_dir}'"
    status_mkdir, _, err_mkdir = session.run(mkdir_cmd, use_sudo=needs_sudo)
    if status_mkdir != 0:
        logger.error(f"{host_prefix} {RED}Falha ao criar diretório {remote_dir}: {err_mkdir}{NC}")
        return

    # --- 2) Conteúdo final desejado ---
    final_content = "HORA_Z=0\n"

    # ---------------- DRY-RUN ----------------
    if getattr(args, "dry_run", False):
        logger.info(f"{host_prefix} {YELLOW}[DRY-RUN]{NC} Nenhuma alteração será feita.")
        logger.info(f"{host_prefix} Arquivo remoto alvo: {remote_conf}")
        logger.info(f"{host_prefix} Conteúdo FINAL que seria aplicado:")
        logger.info(f"{host_prefix} {YELLOW}[DRY-RUN]{NC} HORA_Z=0")
        logger.info(f"{host_prefix} {GREEN}Ação '{ACTION_NAME}' finalizada (dry-run).{NC}")
        return
    # -----------------------------------------

    # --- 3) Envia arquivo temporário e move para /posnet/kwnfce.conf ---
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(final_content)
            local_tmp_path = tmp_file.name

        remote_tmp_path = f"/tmp/{os.path.basename(local_tmp_path)}"
        logger.info(f"{host_prefix} Enviando novo kwnfce.conf para {remote_tmp_path}...")

        session.put(local_tmp_path, remote_tmp_path, use_sudo=needs_sudo)

        mv_cmd = f"mv '{remote_tmp_path}' '{remote_conf}'"
        status_mv, _, err_mv = session.run(mv_cmd, use_sudo=needs_sudo)
        if status_mv != 0:
            logger.error(f"{host_prefix} {RED}Falha ao mover arquivo final: {err_mv}{NC}")
            return

        # --- 4) Ajusta permissões corretas ---
        chown_cmd = f"chown root:root '{remote_conf}'"
        status_chown, _, err_chown = session.run(chown_cmd, use_sudo=needs_sudo)
        if status_chown != 0:
            logger.warning(
                f"{host_prefix} {YELLOW}Falha ao aplicar chown root:root em {remote_conf}: {err_chown}{NC}"
            )

        chmod_cmd = f"chmod 644 '{remote_conf}'"
        status_chmod, _, err_chmod = session.run(chmod_cmd, use_sudo=needs_sudo)
        if status_chmod != 0:
            logger.warning(
                f"{host_prefix} {YELLOW}Falha ao aplicar chmod 644 em {remote_conf}: {err_chmod}{NC}"
            )

        logger.info(
            f"{host_prefix} {GREEN}kwnfce.conf atualizado com sucesso "
            f"(root:root, perm 644).{NC}"
        )

    except Exception as e:
        logger.error(f"{host_prefix} {RED}Erro ao atualizar {remote_conf}: {e}{NC}")
        return

    finally:
        if "local_tmp_path" in locals() and os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)

    logger.info(
        f"{host_prefix} {GREEN}Ação '{ACTION_NAME}' (versão {ACTION_VERSION}) concluída com sucesso.{NC}"
    )
