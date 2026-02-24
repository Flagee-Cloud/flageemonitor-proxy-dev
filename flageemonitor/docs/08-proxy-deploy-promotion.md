# Proxy Deploy Promotion

Fluxo oficial para promover artefatos do ambiente DEV para o repositório de DEPLOY do proxy.

## Script

- `/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh`

## O que o script faz

- valida que o runtime em `proxy/runtime` esta protegido por PyArmor;
- clona o repositório de destino (`flageemonitor-proxy-deploy`);
- aplica allowlist de caminhos permitidos;
- bloqueia conteúdo proibido (`proxy/sources`, `server`, etc.);
- busca padrões de segredo (tokens/chaves privadas);
- cria commit de promoção;
- faz push somente com `--push`.

## Uso

Dry-run (recomendado primeiro):

```bash
/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh --dry-run
```

Promover com push:

```bash
/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh --push
```

Override de remote/branch:

```bash
/ariusmonitor/flageemonitor/tools/release/promote_proxy_deploy.sh \
  --deploy-remote flageemonitor-proxy-deploy \
  --deploy-branch main \
  --push
```

## Requisito obrigatório

Antes de promover, regenerar runtime protegido:

```bash
bash /ariusmonitor/build/build_protegido.sh
```

## Politica

- Conteudo de cliente deve sair somente via `proxy-deploy`.
- Codigo interno (`server`, `proxy/sources`) nao deve ser promovido para deploy.
