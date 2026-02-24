# Release Playbook (Server / Proxy DEV / Image Publish)

Fluxo operacional padrao para publicar conteudo nos repositorios separados do FlageeMonitor.

## Scripts

- Server: `/ariusmonitor/flageemonitor/tools/release/promote_server.sh`
- Proxy DEV: `/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh`
- Publish image: `/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh`

## Ordem recomendada

1. Atualizar codigo e documentacao no workspace principal.
2. Regenerar runtime protegido quando houver mudanca de proxy:
- `bash /ariusmonitor/build/build_protegido.sh`
3. Publicar para `proxy-dev` (interno):
- `/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh --push`
4. Publicar para `server` (interno):
- `/ariusmonitor/flageemonitor/tools/release/promote_server.sh --push`
5. Publicar imagem para cliente:
- `/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh`

## Dry-run obrigatorio

Antes de qualquer push, execute dry-run:

```bash
/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh --dry-run
/ariusmonitor/flageemonitor/tools/release/promote_server.sh --dry-run
```

## Guardrails ativos

- Allowlist por repositorio (somente caminhos permitidos).
- Bloqueio de caminhos proibidos em repos internos.
- Scanner de segredo basico (tokens/chaves privadas).
- Validacao obrigatoria de runtime protegido por PyArmor no publish de imagem.

## Nota sobre imagem Docker

A publicacao da imagem canonicamente usa:

```bash
/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh
```

Tags atuais seguem:

- `ghcr.io/flagee-cloud/flageemonitor-client:<short_sha>`
- `ghcr.io/flagee-cloud/flageemonitor-client:latest`

## Versionamento de release

- Padrao oficial de tag: `flageemonitor-vMAJOR.MINOR.PATCH`
- Guia rapido: `docs/11-versioning-and-release-tags.md`
