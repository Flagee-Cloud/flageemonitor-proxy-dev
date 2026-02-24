FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /ariusmonitor

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        default-mysql-client \
        cron \
        tzdata \
        zabbix-sender \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /ariusmonitor/requirements.txt
RUN pip install --no-cache-dir -r /ariusmonitor/requirements.txt mysql-connector-python

COPY runtime /ariusmonitor/runtime
COPY scripts /ariusmonitor/scripts
COPY host-linux /ariusmonitor/host-linux
COPY postgresql /ariusmonitor/postgresql
COPY utilities /ariusmonitor/utilities
COPY assets/certi_api.pem /ariusmonitor/certi_api.pem
COPY docker/entrypoint.sh /ariusmonitor/entrypoint.sh
COPY docker/run_action.sh /ariusmonitor/run_action.sh
COPY docker/update_config.sh /ariusmonitor/update_config.sh

RUN chmod +x /ariusmonitor/entrypoint.sh /ariusmonitor/run_action.sh /ariusmonitor/update_config.sh \
    && find /ariusmonitor/scripts -type f -name "*.sh" -exec chmod +x {} \; \
    && find /ariusmonitor/utilities -type f -name "*.sh" -exec chmod +x {} \;

ENV ARIUSMONITOR_CONFIG_URL="https://api-ariusmonitor.flagee.cloud/api/ingest/bot/config" \
    ARIUSMONITOR_CONFIG_PATH="/ariusmonitor/config_bot.json" \
    ARIUSMONITOR_CONFIG_CONF="/ariusmonitor/config_bot.conf" \
    RUN_MODE="daemon" \
    TZ="America/Sao_Paulo"

ENTRYPOINT ["/ariusmonitor/entrypoint.sh"]
