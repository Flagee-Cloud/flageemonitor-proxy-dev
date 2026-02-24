FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /flageemonitor

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        default-mysql-client \
        cron \
        tzdata \
        zabbix-sender \
    && rm -rf /var/lib/apt/lists/*

# Runtime atual vem do proxy legado; caminho canonico no container e /flageemonitor.
COPY proxy/requirements.txt /flageemonitor/requirements.txt
RUN pip install --no-cache-dir -r /flageemonitor/requirements.txt mysql-connector-python

COPY proxy/runtime /flageemonitor/runtime
COPY proxy/scripts /flageemonitor/scripts
COPY proxy/host-linux /flageemonitor/host-linux
COPY proxy/postgresql /flageemonitor/postgresql
COPY proxy/utilities /flageemonitor/utilities
COPY assets/certi_api.pem /flageemonitor/certi_api.pem

COPY flageemonitor/proxy/docker/entrypoint.sh /flageemonitor/entrypoint.sh
COPY flageemonitor/proxy/docker/run_action.sh /flageemonitor/run_action.sh
COPY flageemonitor/proxy/docker/update_config.sh /flageemonitor/update_config.sh

# Compatibilidade retroativa: caminho legado continua funcional.
RUN ln -s /flageemonitor /ariusmonitor \
    && chmod +x /flageemonitor/entrypoint.sh /flageemonitor/run_action.sh /flageemonitor/update_config.sh \
    && find /flageemonitor/scripts -type f -name "*.sh" -exec chmod +x {} \; \
    && find /flageemonitor/utilities -type f -name "*.sh" -exec chmod +x {} \;

ENV FLAGEEMONITOR_CONFIG_URL="https://api-ariusmonitor.flagee.cloud/api/ingest/bot/config" \
    FLAGEEMONITOR_CONFIG_PATH="/flageemonitor/config_bot.json" \
    FLAGEEMONITOR_CONFIG_CONF="/flageemonitor/config_bot.conf" \
    RUN_MODE="daemon" \
    TZ="America/Sao_Paulo"

ENTRYPOINT ["/flageemonitor/entrypoint.sh"]
