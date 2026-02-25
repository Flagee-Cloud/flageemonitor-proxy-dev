# Proxy Bootstrap (Docker First)

Bootstrap host-side minimo para executar o proxy em container.

## Objetivo

- Padronizar instalacao e operacao do proxy em modelo Docker First.
- Reduzir dependencia do SO host.
- Permitir bootstrap em Linux e Windows com Docker.

## Linux

Script: `linux/install_flageemonitor.sh`

Opcao recomendada (API entrega script apos validar token):

```bash
curl -fsSL -H "X-Bot-Token: TOKEN_DO_CLIENTE" \
  https://monitor-api.flagee.cloud/api/bootstrap/install.sh \
  | sudo bash -s -- TOKEN_DO_CLIENTE
```

Com Watchtower oficial no fluxo:

```bash
curl -fsSL -H "X-Bot-Token: TOKEN_DO_CLIENTE" \
  https://monitor-api.flagee.cloud/api/bootstrap/install.sh \
  | sudo bash -s -- TOKEN_DO_CLIENTE --with-watchtower --watchtower-interval 300
```

Health do bootstrap:

```bash
curl -fsSL https://monitor-api.flagee.cloud/api/bootstrap/health
```

Exemplo:

```bash
sudo bash install_flageemonitor.sh TOKEN_DO_CLIENTE \
  --runtime-name flageemonitor \
  --image ghcr.io/flagee-cloud/flageemonitor-client:latest
```

Comandos instalados:

- `flageemonitor-update-config`
- `flageemonitor-update-image`
- `flageemonitor-run`
- `flageemonitor-logs`
- `flageemonitor-watchtower-logs`

## Windows

Script: `windows/install_flageemonitor.ps1`

Exemplo:

```powershell
.\install_flageemonitor.ps1 -ClientToken TOKEN_DO_CLIENTE -RuntimeName flageemonitor
```

Wrappers gerados em `C:\ProgramData\FlageeMonitor\bin`.

## Variaveis principais

- `FLAGEEMONITOR_TOKEN`
- `FLAGEEMONITOR_REDE`
- `FLAGEEMONITOR_IMAGE`
- `FLAGEEMONITOR_CONFIG_URL`
- `FLAGEEMONITOR_CONTAINER_ROOT` (default canônico: `/flageemonitor`; legado: `/ariusmonitor`)

## Observacao

Esta base ja e Docker First e host-agnostic. O caminho canônico do runtime e `/flageemonitor`, com suporte legado opcional via `--container-root /ariusmonitor`.
