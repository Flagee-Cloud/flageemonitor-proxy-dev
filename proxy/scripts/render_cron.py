#!/usr/bin/env python3
import json
import os


def as_bool(value, default):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def main():
    config_path = os.environ.get("ARIUSMONITOR_CONFIG_PATH", "/ariusmonitor/config_bot.json")
    cron_path = "/etc/cron.d/ariusmonitor"

    data = {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    cron_flags = data.get("PARAM_CRON_ACTIONS") or {}
    enable_shutdown = as_bool(cron_flags.get("pdv_shutdown"), True)
    enable_status_caixa = as_bool(cron_flags.get("status_caixa"), False)

    lines = [
        "SHELL=/bin/bash",
        "",
        "# Atualiza config",
        "0 * * * * root /ariusmonitor/update_config.sh >> /proc/1/fd/1 2>&1",
        "",
        "# Agente monitoramento",
        "*/30 * * * * root /ariusmonitor/run_action.sh pdv_install --agent-status 2 >> /proc/1/fd/1 2>&1",
        "",
        "# Execucao dos scripts",
        "*/5 * * * * root /ariusmonitor/run_action.sh cupons >> /proc/1/fd/1 2>&1",
        "0 * * * * root /ariusmonitor/run_action.sh cupons_detalhes >> /proc/1/fd/1 2>&1",
        "*/10 7-23 * * * root /ariusmonitor/run_action.sh cupons_lv >> /proc/1/fd/1 2>&1",
        "* 1 * * * root /ariusmonitor/run_action.sh pdv_atualiza_impressora >> /proc/1/fd/1 2>&1",
    ]

    if enable_status_caixa:
        lines.extend(
            [
                "",
                "# Status caixa",
                "*/3 * * * * root /ariusmonitor/run_action.sh status_caixa >> /proc/1/fd/1 2>&1",
            ]
        )

    if enable_shutdown:
        lines.extend(
            [
                "",
                "# DESLIGAR PDVS",
                "50 23 * * * root /bin/bash -lc '/ariusmonitor/run_action.sh pdv_shutdown >> /ariusmonitor/logs/shutdown.log 2>&1'",
            ]
        )

    with open(cron_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


if __name__ == "__main__":
    main()
