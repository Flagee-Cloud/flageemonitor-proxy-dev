# actions/pdv_update_clisitef.py

import os
import logging
import tempfile

from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC

ACTION_NAME = "pdv_update_clisitef"
ACTION_VERSION = "2025-11-24.v4"


def _get_remote_key_value(
    session: SSHSession,
    remote_ini: str,
    section: str,
    key: str,
    needs_sudo: bool,
    logger: logging.Logger,
    host_prefix: str,
) -> str | None:
    """
    Lê o valor ativo de uma chave (key=...) dentro de uma seção específica
    em um arquivo INI remoto.

    Estratégia:
      1) Usa sed para pegar o bloco [section] até a próxima seção (sem usar { }).
      2) Filtra a primeira linha ativa key=... (não comentada).
      3) Se der erro ou vier lixo (ex: mensagem de sed), retorna None.
      4) Se não achar nada, tenta um fallback simples no arquivo inteiro.
    """

    # --- Primeira tentativa: dentro da seção [section] ---
    # IMPORTANTE: sem "{p" para evitar brace expansion/unmatched '{' em shells antigos.
    cmd_block = (
        "sed -n '/^[[:space:]]*\\[" + section + "\\]/,/^[[:space:]]*\\[/p' "
        f"'{remote_ini}' 2>/dev/null | "
        f"grep -E '^[[:space:]]*{key}[[:space:]]*=' | grep -v '^[[:space:]]*[#;]' | "
        "head -n1 | sed 's/^.*=[[:space:]]*//' 2>/dev/null"
    )

    logger.debug(f"{host_prefix} DEBUG {key}: comando (bloco) = {cmd_block}")
    status, out, err = session.run(cmd_block, use_sudo=needs_sudo)

    raw = (out or "").strip()
    logger.debug(
        f"{host_prefix} DEBUG {key} (bloco): status={status}, "
        f"raw_out='{raw}', err='{(err or '').strip()}'"
    )

    value = ""
    if status == 0 and raw and not raw.startswith("sed:"):
        value = raw

    # Se não achar nada ou só vier erro, tenta fallback
    if not value:
        cmd_fallback = (
            f"grep -E '^[[:space:]]*{key}[[:space:]]*=' '{remote_ini}' 2>/dev/null | "
            "grep -v '^[[:space:]]*[#;]' | head -n1 | "
            "sed 's/^.*=[[:space:]]*//' 2>/dev/null"
        )
        logger.debug(f"{host_prefix} DEBUG {key}: comando (fallback) = {cmd_fallback}")
        status_fb, out_fb, err_fb = session.run(cmd_fallback, use_sudo=needs_sudo)

        raw_fb = (out_fb or "").strip()
        logger.debug(
            f"{host_prefix} DEBUG {key} (fallback): status={status_fb}, "
            f"raw_out='{raw_fb}', err='{(err_fb or '').strip()}'"
        )

        if status_fb == 0 and raw_fb and not raw_fb.startswith("sed:"):
            value = raw_fb

    # Se ainda assim não temos valor útil, desiste
    if not value:
        logger.warning(
            f"{host_prefix} {YELLOW}Arquivo {remote_ini} não contém uma chave ativa "
            f"'{key}=' em [{section}] (ou não foi possível extrair).{NC}"
        )
        return None

    logger.info(f"{host_prefix} {key} atual detectado em {remote_ini}: {value}")
    return value

def _build_final_clisitef_content(
    config: dict,
    remote_port: str | None,
    remote_msgpadrao: str | None,
    logger: logging.Logger,
    host_prefix: str,
) -> str:
    """
    Monta o conteúdo final do CliSiTef.ini:

      - Lê CliSiTef.template.ini (sempre).
      - Se remote_port não for None:
          dentro da seção [PinPadCompartilhado], substitui a linha ativa 'Porta=...'
          por 'Porta=<remote_port>'.
      - Se remote_msgpadrao não for None:
          dentro da seção [PinPad], substitui a linha ativa 'MensagemPadrao=...'
          por 'MensagemPadrao=<remote_msgpadrao>'.
      - Se algum dos valores remotos for None:
          mantém o valor do template para aquela chave.
    """
    base_dir = config.get("PARAM_CLISITEF_DIR", "/ariusmonitor/host-linux/clisitef")
    base_path = os.path.join(base_dir, "CliSiTef.template.ini")

    if not os.path.isfile(base_path):
        raise FileNotFoundError(
            f"Template base CliSiTef.template.ini não encontrado em: {base_path}"
        )

    try:
        with open(base_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:
        logger.error(f"{host_prefix} {RED}Falha ao ler template base {base_path}: {e}{NC}")
        raise

    if remote_port is None:
        logger.info(
            f"{host_prefix} Porta remota não encontrada; usando Porta do template base sem alteração."
        )
    if remote_msgpadrao is None:
        logger.info(
            f"{host_prefix} MensagemPadrao remota não encontrada; usando valor do template base."
        )

    new_lines: list[str] = []
    inside_pinpad = False
    inside_pinpadcomp = False
    porta_substituida = False
    msg_substituida = False

    for line in lines:
        stripped = line.strip()

        # Detecta início de seção
        if stripped.startswith("[") and stripped.endswith("]"):
            section_name = stripped.strip("[]")
            inside_pinpad = (section_name == "PinPad")
            inside_pinpadcomp = (section_name == "PinPadCompartilhado")

            new_lines.append(line)
            continue

        # --- Dentro de [PinPad] → MensagemPadrao ---
        if inside_pinpad and remote_msgpadrao is not None:
            if (
                not stripped.startswith("#")
                and not stripped.startswith(";")
                and stripped.startswith("MensagemPadrao")
                and "=" in stripped
            ):
                nova_linha = f"MensagemPadrao={remote_msgpadrao}"
                logger.info(
                    f"{host_prefix} Substituindo MensagemPadrao do template: "
                    f"'{line}' -> '{nova_linha}'"
                )
                new_lines.append(nova_linha)
                msg_substituida = True
                continue

        # --- Dentro de [PinPadCompartilhado] → Porta ---
        if inside_pinpadcomp and remote_port is not None:
            if (
                not stripped.startswith("#")
                and not stripped.startswith(";")
                and stripped.startswith("Porta")
                and "=" in stripped
            ):
                nova_linha = f"Porta={remote_port}"
                logger.info(
                    f"{host_prefix} Substituindo Porta do template: "
                    f"'{line}' -> '{nova_linha}'"
                )
                new_lines.append(nova_linha)
                porta_substituida = True
                continue

        # Demais linhas: mantém como estão
        new_lines.append(line)

    # Warnings se não encontrou as chaves ativas no template
    if remote_port is not None and not porta_substituida:
        logger.warning(
            f"{host_prefix} Não foi encontrada linha Porta= ativa em [PinPadCompartilhado] "
            f"no template. Porta remota ({remote_port}) NÃO foi aplicada."
        )

    if remote_msgpadrao is not None and not msg_substituida:
        logger.warning(
            f"{host_prefix} Não foi encontrada linha MensagemPadrao= ativa em [PinPad] "
            f"no template. MensagemPadrao remota ({remote_msgpadrao}) NÃO foi aplicada."
        )

    return "\n".join(new_lines) + "\n"


def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Action: pdv_update_clisitef

    Fluxo:
      - Conecta no PDV.
      - Lê /posnet/CliSiTef.ini remoto (se existir) para descobrir:
          * Porta atual em [PinPadCompartilhado]
          * MensagemPadrao atual em [PinPad]
      - Gera um novo CliSiTef.ini a partir de CliSiTef.template.ini,
        preservando apenas Porta e MensagemPadrao do host.
      - Cria/sobrescreve /posnet/CliSiTef-bkp.ini.
      - Grava o novo conteúdo em /posnet/CliSiTef.ini.

    Em --dry-run:
      - Conecta, descobre Porta/MensagemPadrao.
      - Gera o conteúdo final.
      - NÃO mexe no host; só mostra o que seria aplicado.
    """
    host_name = host.get("host", "UNKNOWN")
    host_log_prefix = f"[{host_name}]"

    logger.info(
        f"{host_log_prefix} Iniciando ação '{ACTION_NAME}' "
        f"(versão {ACTION_VERSION})..."
    )

    needs_sudo = session.user != "root"
    remote_dir = "/posnet"
    remote_ini = f"{remote_dir}/CliSiTef.ini"
    remote_bkp = f"{remote_dir}/CliSiTef-bkp.ini"

    # 1) Garante diretório /posnet
    mkdir_cmd = f"mkdir -p '{remote_dir}'"
    status_mkdir, _, err_mkdir = session.run(mkdir_cmd, use_sudo=needs_sudo)
    if status_mkdir != 0:
        logger.error(f"{host_log_prefix} {RED}Falha ao criar diretório {remote_dir}: {err_mkdir}{NC}")
        return

    # 2) Descobre valores atuais do CliSiTef.ini remoto (se existir)
    remote_port = _get_remote_key_value(
        session=session,
        remote_ini=remote_ini,
        section="PinPadCompartilhado",
        key="Porta",
        needs_sudo=needs_sudo,
        logger=logger,
        host_prefix=host_log_prefix,
    )

    remote_msgpadrao = _get_remote_key_value(
        session=session,
        remote_ini=remote_ini,
        section="PinPad",
        key="MensagemPadrao",
        needs_sudo=needs_sudo,
        logger=logger,
        host_prefix=host_log_prefix,
    )

    # 3) Gera conteúdo final a partir do template + valores remotos
    try:
        final_content = _build_final_clisitef_content(
            config=config,
            remote_port=remote_port,
            remote_msgpadrao=remote_msgpadrao,
            logger=logger,
            host_prefix=host_log_prefix,
        )
    except Exception:
        logger.error(f"{host_log_prefix} {RED}Falha ao montar conteúdo final do CliSiTef.ini.{NC}")
        return

    # ---------------- DRY-RUN ----------------
    if getattr(args, "dry_run", False):
        logger.info(f"{host_log_prefix} {YELLOW}[DRY-RUN]{NC} Nenhuma alteração será feita no host.")
        logger.info(f"{host_log_prefix} Arquivo remoto alvo: {remote_ini}")
        logger.info(f"{host_log_prefix} Conteúdo FINAL (template + Porta/MensagemPadrao remotas) que seria aplicado:")
        for line in final_content.splitlines():
            logger.info(f"{host_log_prefix} {YELLOW}[DRY-RUN]{NC} {line}")
        logger.info(
            f"{host_log_prefix} {GREEN}Ação '{ACTION_NAME}' finalizada em modo dry-run.{NC}"
        )
        return
    # -----------------------------------------

    # 4) Cria/atualiza backup /posnet/CliSiTef-bkp.ini
    logger.info(f"{host_log_prefix} Criando backup em {remote_bkp}...")

    test_cmd = f"test -f '{remote_ini}'"
    status_test, _, _ = session.run(test_cmd, use_sudo=needs_sudo)

    if status_test == 0:
        cp_cmd = f"cp '{remote_ini}' '{remote_bkp}'"
        status_cp, _, err_cp = session.run(cp_cmd, use_sudo=needs_sudo)
        if status_cp != 0:
            logger.error(f"{host_log_prefix} {RED}Falha ao copiar backup: {err_cp}{NC}")
            return
    else:
        touch_cmd = f": > '{remote_bkp}'"
        status_touch, _, err_touch = session.run(touch_cmd, use_sudo=needs_sudo)
        if status_touch != 0:
            logger.error(f"{host_log_prefix} {RED}Falha ao criar backup vazio: {err_touch}{NC}")
            return

    logger.info(f"{host_log_prefix} {GREEN}Backup criado/atualizado: {remote_bkp}{NC}")

    # 5) Envia o arquivo final para o host
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(final_content)
            local_tmp_path = tmp_file.name

        remote_tmp_path = f"/tmp/{os.path.basename(local_tmp_path)}"
        logger.info(f"{host_log_prefix} Enviando novo CliSiTef.ini para {remote_tmp_path}...")
        session.put(local_tmp_path, remote_tmp_path, use_sudo=needs_sudo)

        mv_cmd = f"mv '{remote_tmp_path}' '{remote_ini}'"
        status_mv, _, err_mv = session.run(mv_cmd, use_sudo=needs_sudo)
        if status_mv != 0:
            logger.error(f"{host_log_prefix} {RED}Falha ao mover arquivo final: {err_mv}{NC}")
            return

        # Garante que o arquivo final fique com root:root e permissão 644
        chown_cmd = f"chown root:root '{remote_ini}'"
        status_chown, _, err_chown = session.run(chown_cmd, use_sudo=needs_sudo)
        if status_chown != 0:
            logger.warning(
                f"{host_log_prefix} {YELLOW}Falha ao aplicar chown root:root em {remote_ini}: {err_chown}{NC}"
            )

        chmod_cmd = f"chmod 644 '{remote_ini}'"
        status_chmod, _, err_chmod = session.run(chmod_cmd, use_sudo=needs_sudo)
        if status_chmod != 0:
            logger.warning(
                f"{host_log_prefix} {YELLOW}Falha ao aplicar chmod 644 em {remote_ini}: {err_chmod}{NC}"
            )

        logger.info(
            f"{host_log_prefix} {GREEN}CliSiTef.ini atualizado com sucesso em {remote_ini} "
            f"(owner root:root, perm 644).{NC}"
        )

    except Exception as e:
        logger.error(f"{host_log_prefix} {RED}Erro no envio do novo CliSiTef.ini: {e}{NC}")
        return
    finally:
        if "local_tmp_path" in locals() and os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)

    logger.info(
        f"{host_log_prefix} {GREEN}Ação '{ACTION_NAME}' (versão {ACTION_VERSION}) "
        f"finalizada com sucesso.{NC}"
    )
