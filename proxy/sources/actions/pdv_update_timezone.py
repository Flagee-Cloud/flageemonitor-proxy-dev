# actions/pdv_update_timezone.py
import logging
from ssh_manager import SSHSession
from utils import GREEN, RED, YELLOW, NC


def _run_cmd(
    session: SSHSession,
    cmd: str,
    needs_sudo: bool,
    logger,
    host_log_prefix,
    allow_fail: bool = False,
    dry_run: bool = False,
):
    if dry_run:
        logger.info(f"{host_log_prefix} {YELLOW}DRY-RUN: executaria '{cmd}'{NC}")
        return True, ""
    status, out, err = session.run(cmd, use_sudo=needs_sudo, logger=logger)
    if status != 0 and not allow_fail:
        logger.error(f"{host_log_prefix} {RED}Falha ao executar '{cmd}'. Erro: {err}{NC}")
        return False, out
    return True, out


def _get_systemd_timezone(session: SSHSession, needs_sudo: bool, timedatectl_path: str):
    if not timedatectl_path:
        return None
    status, out, _ = session.run(
        f"{timedatectl_path} 2>/dev/null | awk -F': *' '/Time zone:/{{print $2}}'",
        use_sudo=needs_sudo,
    )
    if status != 0:
        return None
    return out.strip().split(" ")[0] if out.strip() else None


def _get_timezone_file(session: SSHSession, needs_sudo: bool):
    status, out, _ = session.run("cat /etc/timezone 2>/dev/null", use_sudo=needs_sudo)
    if status != 0:
        return None
    return out.strip()


def _get_localtime_target(session: SSHSession, needs_sudo: bool):
    status, out, _ = session.run("readlink -f /etc/localtime 2>/dev/null", use_sudo=needs_sudo)
    if status != 0:
        return None
    return out.strip()

def _get_timedatectl_status(session: SSHSession, needs_sudo: bool, timedatectl_path: str):
    if not timedatectl_path:
        return ""
    status, out, _ = session.run(f"{timedatectl_path} 2>/dev/null", use_sudo=needs_sudo)
    if status != 0:
        return ""
    return out.strip()

def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False

def _get_rede_setting(config: dict, rede: str, key: str, fallback):
    settings = config.get("PDV_TIMEZONE_SETTINGS") or {}
    rede_settings = settings.get(rede, {}) if isinstance(settings, dict) else {}
    default_settings = settings.get("default", {}) if isinstance(settings, dict) else {}
    if isinstance(rede_settings, dict) and key in rede_settings:
        return rede_settings.get(key)
    if isinstance(default_settings, dict) and key in default_settings:
        return default_settings.get(key)
    return fallback

def _install_ntpdate(session: SSHSession, needs_sudo: bool, logger, host_log_prefix, distro: str, dry_run: bool):
    status_apt, _, _ = session.run(
        "command -v apt-get >/dev/null 2>&1 || test -x /usr/bin/apt-get || test -x /bin/apt-get",
        use_sudo=needs_sudo,
    )
    if distro not in {"ubuntu", "debian"} and status_apt != 0:
        logger.warning(f"{host_log_prefix} {YELLOW}Instalacao automatica do ntpdate nao suportada para {distro}.{NC}")
        return False
    if dry_run:
        logger.info(f"{host_log_prefix} {YELLOW}DRY-RUN: tentaria instalar ntpdate via apt-get.{NC}")
        return True
    install_cmd = (
        "DEBIAN_FRONTEND=noninteractive "
        "apt-get -o APT::Get::Assume-Yes=true "
        "-o Dpkg::Options::=--force-confdef "
        "-o Dpkg::Options::=--force-confold "
        "install --no-install-recommends ntpdate"
    )
    ok, _ = _run_cmd(session, install_cmd, needs_sudo, logger, host_log_prefix, allow_fail=True, dry_run=dry_run)
    return ok


def _configure_timesyncd(
    session: SSHSession,
    needs_sudo: bool,
    logger,
    host_log_prefix,
    ntp_server: str,
    dry_run: bool,
    force_timesyncd: bool,
):
    status_systemctl, systemctl_path, _ = session.run(
        "command -v systemctl 2>/dev/null || true",
        use_sudo=False,
    )
    systemctl_path = systemctl_path.strip()
    if status_systemctl != 0 or not systemctl_path:
        return False

    status_service, _, _ = session.run(
        f"{systemctl_path} list-unit-files 2>/dev/null | grep -q '^systemd-timesyncd.service'",
        use_sudo=needs_sudo,
    )
    if status_service != 0:
        return False

    if force_timesyncd:
        override_cmd = (
            "sh -c \"mkdir -p /etc/systemd/system/systemd-timesyncd.service.d; "
            "printf '%s\\n' '[Unit]' 'ConditionFileIsExecutable=' "
            "> /etc/systemd/system/systemd-timesyncd.service.d/override.conf\""
        )
        _run_cmd(session, override_cmd, needs_sudo, logger, host_log_prefix, allow_fail=True, dry_run=dry_run)
        _run_cmd(
            session,
            f"{systemctl_path} daemon-reload",
            needs_sudo,
            logger,
            host_log_prefix,
            allow_fail=True,
            dry_run=dry_run,
        )

    config_cmd = (
        "sh -c \""
        "if [ -d /etc/systemd ]; then "
        "if [ -f /etc/systemd/timesyncd.conf ]; then "
        "cp -f /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.bak.ariusmonitor 2>/dev/null || true; "
        "fi; "
        "touch /etc/systemd/timesyncd.conf; "
        "sed -i -e '/^NTP=/d' -e '/^FallbackNTP=/d' /etc/systemd/timesyncd.conf; "
        "if ! grep -q '^\\[Time\\]' /etc/systemd/timesyncd.conf; then "
        "printf '%s\\n' '[Time]' >> /etc/systemd/timesyncd.conf; "
        "fi; "
        f"printf '%s\\n' 'NTP={ntp_server}' 'FallbackNTP=' >> /etc/systemd/timesyncd.conf; "
        "fi\""
    )
    _run_cmd(session, config_cmd, needs_sudo, logger, host_log_prefix, allow_fail=True, dry_run=dry_run)

    _run_cmd(
        session,
        f"{systemctl_path} enable --now systemd-timesyncd",
        needs_sudo,
        logger,
        host_log_prefix,
        allow_fail=True,
        dry_run=dry_run,
    )
    _run_cmd(
        session,
        f"{systemctl_path} restart systemd-timesyncd",
        needs_sudo,
        logger,
        host_log_prefix,
        allow_fail=True,
        dry_run=dry_run,
    )
    return True

def _detect_distro(session: SSHSession, needs_sudo: bool):
    cmd = (
        "if [ -f /etc/os-release ]; then "
        "ID=$(awk -F= '/^ID=/{print $2}' /etc/os-release | head -n1 | tr -d '\"'); "
        "VER=$(awk -F= '/^VERSION_ID=/{print $2}' /etc/os-release | head -n1 | tr -d '\"'); "
        "echo ${ID:-unknown}; echo ${VER:-unknown}; "
        "elif [ -x /usr/bin/lsb_release ] || [ -x /bin/lsb_release ]; then "
        "lsb_release -si 2>/dev/null | tr '[:upper:]' '[:lower:]'; "
        "lsb_release -sr 2>/dev/null; "
        "elif [ -f /etc/issue ]; then "
        "head -n 1 /etc/issue | awk '{print tolower($1)}'; "
        "head -n 1 /etc/issue | awk '{print $2}'; "
        "elif [ -f /etc/slackware-version ]; then "
        "echo \"slackware\"; cat /etc/slackware-version; "
        "else echo \"unknown\"; echo \"unknown\"; fi"
    )
    status, out, _ = session.run(cmd, use_sudo=needs_sudo)
    if status != 0:
        return "unknown", "unknown"
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    distro = lines[0] if len(lines) > 0 else "unknown"
    version = lines[1] if len(lines) > 1 else "unknown"
    return distro, version


def run(session: SSHSession, host: dict, config: dict, logger: logging.Logger, args):
    """
    Ajusta o timezone do PDV usando TIMEZONE do config_bot.json.
    Compatibilidade: Slackware 13, Ubuntu 14 a 24.
    """
    host_log_prefix = f"[{host['host']}]"
    logger.info(f"{host_log_prefix} INICIANDO AÇÃO 'pdv_update_timezone'...")

    rede = config.get("PARAM_REDE", "")
    timezone = (
        getattr(args, "timezone", None)
        or _get_rede_setting(config, rede, "timezone", None)
        or config.get("TIMEZONE")
        or ""
    ).strip()
    if not timezone:
        logger.error(f"{host_log_prefix} {RED}TIMEZONE não definido no config_bot.json.{NC}")
        return

    localtime_target = (
        getattr(args, "localtime_target", None)
        or _get_rede_setting(config, rede, "localtime_target", None)
        or config.get("TIMEZONE_LOCALTIME_TARGET")
        or ""
    ).strip()
    dry_run = bool(getattr(args, "dry_run", False))
    if dry_run:
        logger.info(f"{host_log_prefix} {YELLOW}DRY-RUN ativo: nenhuma alteração será aplicada.{NC}")

    needs_sudo = session.user != 'root'
    zoneinfo_path = f"/usr/share/zoneinfo/{timezone}"
    localtime_target = localtime_target or zoneinfo_path

    distro, version = _detect_distro(session, False)
    logger.info(f"{host_log_prefix} Distro detectada: {distro} {version}")

    ok, _ = _run_cmd(session, f"test -e {zoneinfo_path}", needs_sudo, logger, host_log_prefix)
    if not ok:
        logger.error(f"{host_log_prefix} {RED}Timezone inválido: {zoneinfo_path} não existe.{NC}")
        return

    if localtime_target != zoneinfo_path:
        ok_target, _ = _run_cmd(session, f"test -e {localtime_target}", needs_sudo, logger, host_log_prefix)
        if not ok_target:
            logger.error(f"{host_log_prefix} {RED}Timezone inválido: {localtime_target} não existe.{NC}")
            return

    status_timedatectl, timedatectl_path, _ = session.run(
        "command -v timedatectl 2>/dev/null "
        "|| (test -x /bin/timedatectl && echo /bin/timedatectl) "
        "|| (test -x /usr/bin/timedatectl && echo /usr/bin/timedatectl) "
        "|| true",
        use_sudo=False,
    )
    timedatectl_path = timedatectl_path.strip()
    if timedatectl_path:
        current_tz = _get_systemd_timezone(session, needs_sudo, timedatectl_path)
        if current_tz == timezone:
            logger.info(f"{host_log_prefix} {GREEN}Timezone já está em {timezone}.{NC}")

        logger.info(f"{host_log_prefix} Ajustando timezone via timedatectl para {timezone}...")
        ok_set, _ = _run_cmd(
            session,
            f"{timedatectl_path} set-timezone {timezone}",
            needs_sudo,
            logger,
            host_log_prefix,
            allow_fail=True,
            dry_run=dry_run,
        )
        if not dry_run:
            if ok_set:
                new_tz = _get_systemd_timezone(session, needs_sudo, timedatectl_path)
                if new_tz == timezone:
                    logger.info(f"{host_log_prefix} {GREEN}Timezone ajustado para {timezone}.{NC}")
                else:
                    logger.warning(f"{host_log_prefix} {YELLOW}timedatectl não confirmou a mudança. Aplicando fallback manual.{NC}")
            else:
                logger.warning(f"{host_log_prefix} {YELLOW}timedatectl falhou. Aplicando fallback manual.{NC}")

    current_file_tz = _get_timezone_file(session, needs_sudo)
    current_localtime = _get_localtime_target(session, needs_sudo)
    if current_localtime == localtime_target and (not current_file_tz or current_file_tz == timezone):
        logger.info(f"{host_log_prefix} {GREEN}Timezone já está alinhado com {timezone}.{NC}")

    logger.info(f"{host_log_prefix} Ajustando timezone manualmente para {timezone}...")
    _run_cmd(session, "rm -f /etc/localtime", needs_sudo, logger, host_log_prefix, allow_fail=True, dry_run=dry_run)
    if not _run_cmd(
        session,
        f"ln -s {localtime_target} /etc/localtime",
        needs_sudo,
        logger,
        host_log_prefix,
        dry_run=dry_run,
    ):
        return
    if distro != "slackware":
        _run_cmd(
            session,
            f"sh -c \"printf '%s\\\\n' '{timezone}' > /etc/timezone\"",
            needs_sudo,
            logger,
            host_log_prefix,
            allow_fail=True,
            dry_run=dry_run,
        )
    else:
        logger.info(f"{host_log_prefix} Slackware detectado. Mantendo somente /etc/localtime.")

    if not dry_run:
        new_localtime = _get_localtime_target(session, needs_sudo)
        if new_localtime == localtime_target:
            logger.info(f"{host_log_prefix} {GREEN}Timezone ajustado para {timezone}.{NC}")
        else:
            logger.error(f"{host_log_prefix} {RED}Falha ao ajustar timezone. Verifique /etc/localtime.{NC}")

    enable_ntp = None
    if hasattr(args, "enable_ntp"):
        enable_ntp = getattr(args, "enable_ntp", None)
    if enable_ntp is None:
        enable_ntp = _get_rede_setting(config, rede, "enable_ntp", None)
    if enable_ntp is None:
        enable_ntp = config.get("NTP_ENABLE")
    enable_ntp = _as_bool(enable_ntp)
    ntp_server = None
    if hasattr(args, "ntp_server"):
        ntp_server = getattr(args, "ntp_server", None)
    if ntp_server is None:
        ntp_server = _get_rede_setting(config, rede, "ntp_server", None)
    if ntp_server is None:
        ntp_server = config.get("NTP_SERVER")
    ntp_server = (ntp_server or "").strip()

    if enable_ntp:
        force_timesyncd = _as_bool(_get_rede_setting(config, rede, "force_timesyncd", False))
        if timedatectl_path and ntp_server:
            _configure_timesyncd(
                session,
                needs_sudo,
                logger,
                host_log_prefix,
                ntp_server,
                dry_run,
                force_timesyncd,
            )
        if timedatectl_path:
            _run_cmd(
                session,
                f"{timedatectl_path} set-ntp on",
                needs_sudo,
                logger,
                host_log_prefix,
                allow_fail=True,
                dry_run=dry_run,
            )
            _run_cmd(
                session,
                f"{timedatectl_path} set-local-rtc 0",
                needs_sudo,
                logger,
                host_log_prefix,
                allow_fail=True,
                dry_run=dry_run,
            )
        else:
            logger.warning(f"{host_log_prefix} {YELLOW}timedatectl não encontrado. Ignorando set-ntp.{NC}")

        if ntp_server:
            status_ntpdate, ntp_path, _ = session.run(
                "command -v ntpdate 2>/dev/null || true",
                use_sudo=needs_sudo,
            )
            ntp_path = ntp_path.strip()
            if status_ntpdate != 0 or not ntp_path:
                _install_ntpdate(session, needs_sudo, logger, host_log_prefix, distro, dry_run)
                status_ntpdate, ntp_path, _ = session.run(
                    "command -v ntpdate 2>/dev/null || true",
                    use_sudo=needs_sudo,
                )
                ntp_path = ntp_path.strip()
            if not ntp_path:
                status_ntpdate, _, _ = session.run(
                    "test -x /usr/sbin/ntpdate && echo /usr/sbin/ntpdate",
                    use_sudo=needs_sudo,
                )
                if status_ntpdate == 0:
                    ntp_path = "/usr/sbin/ntpdate"
            if ntp_path:
                _run_cmd(
                    session,
                    f"{ntp_path} -u {ntp_server}",
                    needs_sudo,
                    logger,
                    host_log_prefix,
                    allow_fail=True,
                    dry_run=dry_run,
                )
            else:
                logger.warning(f"{host_log_prefix} {YELLOW}ntpdate não encontrado. Ignorando sincronização NTP.{NC}")
        else:
            logger.warning(f"{host_log_prefix} {YELLOW}NTP habilitado, mas NTP_SERVER não definido.{NC}")

    if dry_run:
        return

    final_localtime = _get_localtime_target(session, needs_sudo) or "indisponivel"
    final_timezone_file = _get_timezone_file(session, needs_sudo) or "indisponivel"
    td_status = _get_timedatectl_status(session, False, timedatectl_path)
    if td_status:
        logger.info(f"{host_log_prefix} Status timedatectl:\\n{td_status}")
    logger.info(
        f"{host_log_prefix} Resumo: /etc/localtime -> {final_localtime}; /etc/timezone -> {final_timezone_file}"
    )

    if ntp_server:
        status_ntpdate, ntp_path, _ = session.run(
            "command -v ntpdate 2>/dev/null || test -x /usr/sbin/ntpdate && echo /usr/sbin/ntpdate || true",
            use_sudo=needs_sudo,
        )
        ntp_path = ntp_path.strip()
        if status_ntpdate == 0 and ntp_path:
            _run_cmd(
                session,
                f"{ntp_path} -q {ntp_server}",
                needs_sudo,
                logger,
                host_log_prefix,
                allow_fail=True,
                dry_run=False,
            )
