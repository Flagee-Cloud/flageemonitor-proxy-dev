import json
import logging
import os
import re
from functools import lru_cache

from actions import resolve_action_name

LEVEL_RANK = {"L1": 3, "L2": 2, "L3": 1}
DEFAULT_MODE = "warn"
DEFAULT_ENDPOINT_MATRIX = {
    "version": 1,
    "matrix": [
        {"distro": "slackware", "versions": ["13.x"], "arch": ["x86_64", "i686"], "level": "L2"},
        {"distro": "ubuntu", "versions": ["14.04", "16.04"], "arch": ["x86_64", "i686"], "level": "L2"},
        {"distro": "ubuntu", "versions": ["18.04+", "20.04", "22.04", "24.04"], "arch": ["x86_64"], "level": "L1"},
        {"distro": "ubuntu", "versions": ["18.04+", "20.04", "22.04", "24.04"], "arch": ["i686"], "level": "L2"},
        {"distro": "mint", "versions": ["17.x"], "arch": ["x86_64", "i686"], "level": "L2"},
        {"distro": "mint", "versions": ["21.x"], "arch": ["x86_64"], "level": "L1"},
    ],
}
DEFAULT_ACTION_CAPABILITIES = {
    "version": 1,
    "defaults": {"minimum_level": "L2"},
    "rules": {
        "collect_coupons": {"minimum_level": "L3"},
        "collect_coupon_details": {"minimum_level": "L3"},
        "collect_coupon_lv": {"minimum_level": "L3"},
        "collect_sat_config": {"minimum_level": "L3"},
        "collect_checkout_status": {"minimum_level": "L3"},
        "diagnose_env": {"minimum_level": "L3"},
        "install_endpoint_agent": {"minimum_level": "L2"},
        "uninstall_endpoint_agent": {"minimum_level": "L2"},
        "update_endpoint_config": {"minimum_level": "L2"},
        "update_endpoint_timezone": {"minimum_level": "L2"},
        "shutdown_endpoint": {"minimum_level": "L2"},
        "test_endpoint_connection": {"minimum_level": "L2"},
        "test_endpoint_privilege": {"minimum_level": "L2"},
        "refresh_endpoint_printer": {"minimum_level": "L2"},
        "register_endpoints": {"minimum_level": "L2"},
    },
}


def _safe_float(value: str):
    try:
        return float(value)
    except Exception:
        return None


def _parse_os_release(raw: str) -> dict:
    info = {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        info[key.strip()] = value.strip().strip('"')
    return info


def _normalize_distro(os_release: dict) -> str:
    distro = (os_release.get("ID") or "").strip().lower()
    if distro in {"linuxmint", "mint"}:
        return "mint"
    if "slack" in distro:
        return "slackware"
    if distro == "ubuntu":
        return "ubuntu"
    return distro or "unknown"


def _normalize_arch(raw_arch: str) -> str:
    arch = (raw_arch or "").strip().lower()
    if arch in {"x86_64", "amd64"}:
        return "x86_64"
    if arch in {"i386", "i486", "i586", "i686", "x86"}:
        return "i686"
    return arch or "unknown"


def _version_matches(version: str, pattern: str) -> bool:
    version = (version or "").strip()
    pattern = (pattern or "").strip()
    if not version or not pattern:
        return False

    if pattern.endswith(".x"):
        return version.startswith(pattern[:-1])

    if pattern.endswith("+"):
        base = pattern[:-1]
        v = _safe_float(re.match(r"^\d+(?:\.\d+)?", version).group(0)) if re.match(r"^\d+(?:\.\d+)?", version) else None
        b = _safe_float(base)
        return v is not None and b is not None and v >= b

    return version.startswith(pattern)


@lru_cache(maxsize=1)
def _load_endpoint_matrix() -> dict:
    path = os.path.join(os.path.dirname(__file__), "compatibility", "endpoint_matrix.v1.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_ENDPOINT_MATRIX


@lru_cache(maxsize=1)
def _load_action_capabilities() -> dict:
    path = os.path.join(os.path.dirname(__file__), "compatibility", "action_capabilities.v1.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_ACTION_CAPABILITIES


def _resolve_support_level(distro: str, version: str, arch: str) -> str | None:
    matrix = _load_endpoint_matrix().get("matrix", [])
    for row in matrix:
        if row.get("distro") != distro:
            continue
        if arch not in set(row.get("arch", [])):
            continue
        for pattern in row.get("versions", []):
            if _version_matches(version, pattern):
                return row.get("level")
    return None


def _required_level_for_action(canonical_action: str) -> str:
    caps = _load_action_capabilities()
    rules = caps.get("rules", {})
    defaults = caps.get("defaults", {})
    return rules.get(canonical_action, {}).get("minimum_level", defaults.get("minimum_level", "L2"))


def _detect_host_facts(session) -> dict:
    cmd = "sh -c 'uname -m 2>/dev/null; cat /etc/os-release 2>/dev/null || true'"
    _, out, _ = session.run(cmd)
    lines = (out or "").splitlines()
    arch_raw = lines[0].strip() if lines else ""
    os_release_raw = "\n".join(lines[1:]) if len(lines) > 1 else ""

    os_release = _parse_os_release(os_release_raw)
    distro = _normalize_distro(os_release)
    version = (os_release.get("VERSION_ID") or "").strip().strip('"')
    arch = _normalize_arch(arch_raw)

    return {
        "distro": distro,
        "version": version,
        "arch": arch,
        "raw": {
            "arch": arch_raw,
            "os_release": os_release,
        },
    }


def _resolve_mode(config: dict, args) -> str:
    arg_mode = getattr(args, "compat_mode", None)
    if arg_mode:
        return arg_mode
    cfg_mode = (config.get("PARAM_COMPATIBILITY_MODE") or DEFAULT_MODE).strip().lower()
    if cfg_mode in {"off", "warn", "enforce"}:
        return cfg_mode
    return DEFAULT_MODE


def run_compatibility_precheck(session, host: dict, action: str, config: dict, args, logger: logging.Logger) -> bool:
    mode = _resolve_mode(config, args)
    if mode == "off":
        return True

    resolved_action, canonical_action, _ = resolve_action_name(action)
    required_level = _required_level_for_action(canonical_action)

    facts = _detect_host_facts(session)
    support_level = _resolve_support_level(facts["distro"], facts["version"], facts["arch"])

    host_prefix = f"[{host.get('host', host.get('ip', 'host'))}]"

    if not support_level:
        msg = (
            f"{host_prefix} Compatibilidade desconhecida para {facts['distro']} {facts['version']} {facts['arch']} "
            f"(acao '{resolved_action}', canonica '{canonical_action}')."
        )
        if mode == "enforce":
            logger.error(msg + " Bloqueado (modo enforce).")
            return False
        logger.warning(msg + " Seguindo em modo warn.")
        return True

    if LEVEL_RANK.get(support_level, 0) < LEVEL_RANK.get(required_level, 0):
        msg = (
            f"{host_prefix} Ambiente {facts['distro']} {facts['version']} {facts['arch']} nivel {support_level} "
            f"abaixo do minimo {required_level} para acao '{resolved_action}' (canonica '{canonical_action}')."
        )
        if mode == "enforce":
            logger.error(msg + " Bloqueado.")
            return False
        logger.warning(msg + " Seguindo em modo warn.")
        return True

    logger.info(
        f"{host_prefix} Compatibilidade OK: {facts['distro']} {facts['version']} {facts['arch']} "
        f"nivel {support_level} para acao '{resolved_action}' (minimo {required_level})."
    )
    return True
