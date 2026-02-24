# Repositories and Access Model

Este documento define a separacao entre repositorios internos e repositorios usados para deploy no ambiente do cliente.

## Repositorios oficiais

1. Server (interno, nunca visivel ao cliente)
- `git@github.com:Flagee-Cloud/flageemonitor-server.git`

2. Proxy DEV (interno de desenvolvimento)
- `git@github.com:Flagee-Cloud/flageemonitor-proxy-dev.git`

3. Proxy DEPLOY (artefatos/estrutura para ambiente cliente)
- `git@github.com:Flagee-Cloud/flageemonitor-proxy-deploy.git`

## Politica de visibilidade

- `flageemonitor-server`: acesso apenas equipe interna Flagee.
- `flageemonitor-proxy-dev`: privado interno (codigo/fundacao/iteracao).
- `flageemonitor-proxy-deploy`: privado, mas preparado para operacao em cliente (conteudo minimo de deploy).

## Chaves e autenticacao

- Todos os repos usam a mesma chave SSH ja utilizada no legado `Flagee-Cloud/ariusmonitor`.
- Preferir URLs SSH (`git@github.com:...`) para padronizar CI/CD e operacao.

## Diretriz operacional

- Build e validacao ocorrem em `proxy-dev`.
- Publicacao controlada promove conteudo para `proxy-deploy`.
- Cliente consome apenas `proxy-deploy`.
- Nenhum fluxo de cliente deve depender de `flageemonitor-server`.

## Compatibilidade com legado

No script legado `proxy/scripts/gitclone.sh`, o repositorio default passou a ser:

- `git@github.com:Flagee-Cloud/flageemonitor-proxy-deploy.git`

Com overrides opcionais:

- `FLAGEEMONITOR_DEPLOY_REPO_URL`
- `FLAGEEMONITOR_DEPLOY_REPO_BRANCH`

## Promocao DEV -> DEPLOY

- Use o fluxo documentado em `docs/08-proxy-deploy-promotion.md`.
- A promocao usa allowlist e valida PyArmor antes de publicar.
