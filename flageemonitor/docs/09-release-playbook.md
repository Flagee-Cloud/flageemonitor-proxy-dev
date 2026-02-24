# Release Playbook (Server / Proxy DEV / Proxy DEPLOY)

Fluxo operacional padrao para publicar conteudo nos repositorios separados do FlageeMonitor.

## Scripts

- Server: `/ariusmonitor/flageemonitor/tools/release/promote_server.sh`
- Proxy DEV: `/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh`
- Proxy DEPLOY: `/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh`

## Ordem recomendada

1. Atualizar codigo e documentacao no workspace principal.
2. Regenerar runtime protegido quando houver mudanca de proxy:
- `bash /ariusmonitor/build/build_protegido.sh`
3. Publicar para `proxy-dev` (interno):
- `/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh --push`
4. Publicar para `server` (interno):
- `/ariusmonitor/flageemonitor/tools/release/promote_server.sh --push`
5. Promover para `proxy-deploy` (cliente):
- `/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh --push`

## Dry-run obrigatorio

Antes de qualquer push, execute dry-run:

```bash
/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh --dry-run
/ariusmonitor/flageemonitor/tools/release/promote_server.sh --dry-run
/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh --dry-run
```

## Guardrails ativos

- Allowlist por repositorio (somente caminhos permitidos).
- Bloqueio de caminhos proibidos (ex.: codigo interno em repo de deploy).
- Scanner de segredo basico (tokens/chaves privadas).
- No caso de `proxy-deploy`, validacao obrigatoria de runtime protegido por PyArmor.

## Nota sobre imagem Docker

A publicacao da imagem canonicamente usa:

```bash
/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh
```

Tags atuais seguem:

- `ghcr.io/flagee-cloud/flageemonitor-client:<short_sha>`
- `ghcr.io/flagee-cloud/flageemonitor-client:latest`
