# Repositories and Access Model

Este documento define a separacao entre repositorios internos e artefatos de deploy no ambiente do cliente.

## Repositorios oficiais

1. Server (interno, nunca visivel ao cliente)
- `git@github.com:Flagee-Cloud/flageemonitor-server.git`

2. Proxy DEV (interno de desenvolvimento)
- `git@github.com:Flagee-Cloud/flageemonitor-proxy-dev.git`

## Politica de visibilidade

- `flageemonitor-server`: acesso apenas equipe interna Flagee.
- `flageemonitor-proxy-dev`: privado interno (codigo/fundacao/iteracao).

## Chaves e autenticacao

- Todos os repos usam a mesma chave SSH ja utilizada no legado `Flagee-Cloud/ariusmonitor`.
- Preferir URLs SSH (`git@github.com:...`) para padronizar CI/CD e operacao.

## Diretriz operacional

- Build e validacao ocorrem em `proxy-dev`.
- Publicacao cliente ocorre via imagem no GHCR.
- Cliente consome apenas imagem versionada.
- Nenhum fluxo de cliente deve depender de `flageemonitor-server`.

## Publicacao de cliente

- Use `flageemonitor/proxy/scripts/docker/publish_image.sh`.
- O script valida runtime protegido por PyArmor antes de publicar.
