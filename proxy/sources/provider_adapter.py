#!/usr/bin/env python3

import hashlib
import logging
from typing import Optional

from actions import resolve_action_name

# Translation of provider-specific external action names to canonical names.
PROVIDER_ACTION_TRANSLATIONS = {
    "zanthus": {
        "install_terminal_agent": "install_endpoint_agent",
        "remove_terminal_agent": "uninstall_endpoint_agent",
        "sync_terminal_config": "update_endpoint_config",
        "sync_terminal_timezone": "update_endpoint_timezone",
        "terminal_shutdown": "shutdown_endpoint",
        "terminal_ping": "test_endpoint_connection",
        "terminal_privilege_check": "test_endpoint_privilege",
        "terminal_printer_refresh": "refresh_endpoint_printer",
        "terminals_register": "register_endpoints",
    }
}


def normalize_provider(provider: Optional[str]) -> str:
    value = (provider or "").strip().lower()
    return value if value else "arius"


def resolve_provider(config: dict, args) -> str:
    # Priority: CLI arg > config > default (arius)
    cli_provider = getattr(args, "provider", None)
    cfg_provider = config.get("PARAM_PROVIDER")
    return normalize_provider(cli_provider or cfg_provider)


def _rollout_percent_for_provider(provider: str, config: dict) -> int:
    # 1) provider-specific explicit key: PARAM_ROLLOUT_<PROVIDER>
    provider_key = f"PARAM_ROLLOUT_{provider.upper()}"
    raw = config.get(provider_key)

    # 2) generic map key: PARAM_PROVIDER_ROLLOUT={"zanthus":20}
    if raw is None:
        rollout_map = config.get("PARAM_PROVIDER_ROLLOUT")
        if isinstance(rollout_map, dict):
            raw = rollout_map.get(provider)

    # 3) generic fallback: PARAM_PROVIDER_ROLLOUT=<int>
    if raw is None and isinstance(config.get("PARAM_PROVIDER_ROLLOUT"), int):
        raw = config.get("PARAM_PROVIDER_ROLLOUT")

    # Defaults keep legacy provider fully enabled and others disabled until explicit rollout.
    if raw is None:
        raw = 100 if provider == "arius" else 0

    try:
        pct = int(raw)
    except (TypeError, ValueError):
        pct = 0 if provider != "arius" else 100

    return max(0, min(100, pct))


def _host_bucket(host: dict) -> int:
    host_key = f"{host.get('host', '')}|{host.get('ip', '')}|{host.get('user', '')}"
    digest = hashlib.sha1(host_key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def is_host_in_rollout(provider: str, config: dict, host: dict) -> tuple[bool, int, int]:
    pct = _rollout_percent_for_provider(provider, config)

    if pct >= 100:
        return True, pct, 0

    bucket = _host_bucket(host)
    return bucket < pct, pct, bucket


def translate_action_for_provider(action: str, provider: str, logger: logging.Logger) -> tuple[str, bool]:
    provider = normalize_provider(provider)
    translations = PROVIDER_ACTION_TRANSLATIONS.get(provider, {})
    translated = translations.get((action or "").strip(), action)

    if translated != action:
        logger.info(
            "Action provider-specific '%s' (%s) traduzida para '%s'.",
            action,
            provider,
            translated,
        )
        return translated, True

    return action, False


def resolve_effective_action_for_host(
    resolved_action: str,
    canonical_action: str,
    provider: str,
    config: dict,
    host: dict,
    logger: logging.Logger,
) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (effective_module_action, skip_reason).

    - For provider in rollout, keeps current action (or can route to override later).
    - For provider out of rollout, returns skip reason.
    """
    provider = normalize_provider(provider)

    enabled, pct, bucket = is_host_in_rollout(provider, config, host)
    if not enabled:
        return None, (
            f"Provider '{provider}' fora do rollout para host (bucket={bucket}, rollout={pct}%)."
        )

    # Hook point for future provider-specific implementation overrides.
    # For now we keep the same action module selected by canonical/legacy map.
    override_name = config.get("PARAM_PROVIDER_ACTION_OVERRIDES", {})
    if isinstance(override_name, dict):
        provider_overrides = override_name.get(provider, {})
        if isinstance(provider_overrides, dict):
            candidate = provider_overrides.get(canonical_action)
            if isinstance(candidate, str) and candidate.strip():
                module_candidate = candidate.strip()
                resolved_candidate, _, _ = resolve_action_name(module_candidate)
                logger.info(
                    "Provider '%s' override de action: '%s' -> '%s'.",
                    provider,
                    resolved_action,
                    resolved_candidate,
                )
                return resolved_candidate, None

    return resolved_action, None
