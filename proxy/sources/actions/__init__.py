ACTION_VERSIONS = {
    "cupons": "1.0.0",
    "cupons_detalhes": "1.0.0",
    "cupons_lv": "1.0.0",
    "diagnose_env": "1.0.0",
    "pdv_atualiza_impressora": "1.0.0",
    "pdv_auto_register": "1.0.3",
    "pdv_install": "1.0.0",
    "pdv_shutdown": "1.0.1",
    "pdv_test_connection": "1.0.0",
    "pdv_test_sudo": "1.0.0",
    "pdv_uninstall": "1.0.0",
    "pdv_update_clisitef": "1.0.0",
    "pdv_update_config": "1.0.0",
    "pdv_update_geral_conf": "1.0.0",
    "pdv_update_kwnfce": "1.0.0",
    "pdv_update_timezone": "1.0.13",
    "sat_config": "1.0.0",
    "status_caixa": "1.0.0"
}

# Canonical action names (vendor-neutral) mapped to current module names.
CANONICAL_ACTION_MAP = {
    "install_endpoint_agent": "pdv_install",
    "uninstall_endpoint_agent": "pdv_uninstall",
    "update_endpoint_config": "pdv_update_config",
    "update_endpoint_timezone": "pdv_update_timezone",
    "shutdown_endpoint": "pdv_shutdown",
    "test_endpoint_connection": "pdv_test_connection",
    "test_endpoint_privilege": "pdv_test_sudo",
    "refresh_endpoint_printer": "pdv_atualiza_impressora",
    "register_endpoints": "pdv_auto_register",
    "collect_coupons": "cupons",
    "collect_coupon_details": "cupons_detalhes",
    "collect_coupon_lv": "cupons_lv",
    "collect_sat_config": "sat_config",
    "collect_checkout_status": "status_caixa",
}

LEGACY_TO_CANONICAL = {legacy: canonical for canonical, legacy in CANONICAL_ACTION_MAP.items()}


def resolve_action_name(action: str) -> tuple[str, str, bool]:
    """
    Resolve requested action to:
    - executable module action name (legacy/current module filename)
    - canonical action name
    - whether resolution happened via alias
    """
    normalized = (action or "").strip()

    if normalized in CANONICAL_ACTION_MAP:
        resolved = CANONICAL_ACTION_MAP[normalized]
        return resolved, normalized, True

    canonical = LEGACY_TO_CANONICAL.get(normalized, normalized)
    return normalized, canonical, False


def list_supported_action_names(module_actions: list[str]) -> list[str]:
    names = set(module_actions or [])
    names.update(CANONICAL_ACTION_MAP.keys())
    return sorted(names)


def get_action_version(action: str) -> str:
    resolved, _, _ = resolve_action_name(action)
    return ACTION_VERSIONS.get(resolved, "unknown")
