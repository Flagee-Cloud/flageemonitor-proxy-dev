# Proxy Deploy Promotion (Descontinuado)

Este fluxo foi descontinuado.

## Motivo

- O repositorio `flageemonitor-proxy` agora e image-only.
- Nao promovemos mais runtime/scripts para repositorio de cliente.

## Fluxo atual

1. Regenerar runtime protegido:

```bash
bash /ariusmonitor/build/build_protegido.sh
```

2. Publicar imagem:

```bash
/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh
```

## Observacao

- O script `tools/release/promote_proxy_deploy.sh` permanece apenas por compatibilidade historica e retorna erro orientando o novo fluxo.
