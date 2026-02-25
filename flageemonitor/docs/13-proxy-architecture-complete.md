# FlageeMonitor Proxy Architecture (Complete)

Este documento descreve a arquitetura completa do Proxy no modelo atual de producao.

## 1. Escopo

- Produto: `FlageeMonitor Proxy`
- Modelo: `Docker First`
- Artefato de deploy: imagem em GHCR
- Controle de update no cliente: `Watchtower` (obrigatorio)

## 2. Visao de alto nivel

Fluxo principal:

1. Server valida token do cliente e entrega bootstrap (`/api/bootstrap/install.sh`).
2. Host cliente instala wrappers e sobe container do proxy.
3. Proxy baixa/atualiza `config_bot.json` da API.
4. Proxy executa actions locais/remotas conforme agenda/config.
5. Watchtower monitora imagem e atualiza runtime automaticamente.

## 3. Componentes e papeis

### 3.1 Control Plane (Server)

- API de bootstrap:
  - `GET /api/bootstrap/install.sh`
  - `GET /api/bootstrap/health`
- API de config do bot:
  - `GET /api/ingest/bot/config`
- Validacao de token de cliente:
  - Header `X-Bot-Token` ou `Authorization: Bearer ...`
- Papel:
  - distribuir bootstrap e configuracao autorizada por cliente/rede.

### 3.2 Data Plane (Cliente)

- Container principal:
  - imagem `ghcr.io/flagee-cloud/flageemonitor-client:<tag>`
  - runtime em `/flageemonitor` (compat: symlink `/ariusmonitor`)
- Container de update:
  - `containrrr/watchtower`
  - nome: `${runtime_name}-watchtower`
  - papel: atualizar o container principal ao detectar nova imagem.

### 3.3 Host-side wrappers

No Linux:
- `flageemonitor-update-config`
- `flageemonitor-update-image`
- `flageemonitor-run`
- `flageemonitor-logs`
- `flageemonitor-watchtower-logs`

No Windows:
- `flageemonitor-run.ps1`
- `flageemonitor-logs.ps1`
- `flageemonitor-watchtower-logs.ps1`

## 4. Conteudo da imagem do proxy

Diretorio canonico no container: `/flageemonitor`

Principais blocos:
- `runtime/`: codigo protegido (PyArmor) do executor de actions.
- `scripts/`: scripts auxiliares (render de cron e utilitarios legados).
- `utilities/`, `host-linux/`, `postgresql/`: ativos de suporte.
- `entrypoint.sh`: orquestra startup e modo daemon/manual.
- `run_action.sh`: executa action sob demanda.
- `update_config.sh`: refresh de config a partir da API.

## 5. Ciclo de vida de runtime

### 5.1 Install

1. bootstrap valida token e baixa config inicial.
2. escreve env/config no host (`/etc/flageemonitor` no Linux).
3. executa update inicial:
  - sobe container principal
  - sobe container watchtower (obrigatorio)

### 5.2 Operacao continua

- runtime roda em modo daemon por default.
- cron interno dispara actions conforme `config_bot.json`.
- operador pode forcar run manual com `flageemonitor-run <action>`.

### 5.3 Update

- via watchtower (automatico) ou `flageemonitor-update-image` (manual).
- update sempre considera runtime + watchtower juntos.

## 6. Pipeline interno de execucao de action

1. `main.py` recebe action e filtros.
2. resolve provider efetivo (`arius` default) e traduz naming externo.
3. resolve action canonica e alias legado.
4. seleciona hosts no Zabbix.
5. `process_one.py` aplica:
  - rollout por provider
  - precheck de compatibilidade por SO/arquitetura
  - execucao do modulo de action.

## 7. Provider architecture (multi-software-house)

Objetivo:
- mesmo proxy para Arius, Zanthus e futuros providers.

Mecanismos:
- naming canonico de actions no core.
- traducao provider-specific -> canonico.
- rollout percentual por provider/host.
- overrides por provider apenas quando necessario.

Defaults:
- `arius`: 100%
- providers novos: 0% ate habilitacao explicita.

## 8. Compatibilidade de endpoint

Camada `compatibility_guard`:
- detecta distro/version/arch do host remoto.
- cruza com matriz de compatibilidade.
- aplica politica por modo:
  - `off`
  - `warn`
  - `enforce`

Beneficio:
- reduz quebra em parque heterogeneo (Slackware/Ubuntu/Mint, 32/64 bits).

## 9. Seguranca

- Bootstrap e config protegidos por token de cliente.
- Runtime de producao protegido por PyArmor (gate no publish).
- Separacao de superficies:
  - codigo fonte em repos internos
  - deploy cliente via imagem GHCR.

## 10. Artefatos e repositorios

- `flageemonitor-proxy-dev`: codigo fonte do proxy.
- `flageemonitor-server`: codigo fonte do server.
- GHCR (`flageemonitor-client`): artefato de producao consumido pelo cliente.

## 11. Operacao e observabilidade

Checks basicos no cliente:
- `docker ps | rg '<runtime>|<runtime>-watchtower'`
- `flageemonitor-logs`
- `flageemonitor-watchtower-logs`
- `flageemonitor-run diagnose_env`

Checks basicos no server:
- `/health`
- `/api/bootstrap/health`

## 12. Falhas comuns e recuperacao

- Token invalido:
  - erro 401/403 em bootstrap/config.
  - corrigir token/rede do cliente.
- Wrapper apontando para runtime errado:
  - corrigir `FLAGEEMONITOR_RUNTIME_NAME` no env.
- Watchtower ausente:
  - rerun bootstrap ou `flageemonitor-update-image`.
- Config indisponivel:
  - manter ultimo `config_bot.json` valido e reexecutar update-config.

