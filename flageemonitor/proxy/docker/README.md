# FlageeMonitor Proxy Image

Imagem canônica do proxy com runtime em `/flageemonitor`.

## Compatibilidade

- Mantem link simbolico `/ariusmonitor -> /flageemonitor` para transicao.
- Aceita variaveis `FLAGEEMONITOR_*` e fallback para `ARIUSMONITOR_*`.

## Build local

```bash
docker build -f /ariusmonitor/flageemonitor/proxy/docker/Dockerfile -t flageemonitor-client:dev /ariusmonitor
```

## Publicacao

Use:

- `/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh`

## Politica de seguranca de release

- Publicacao de imagem falha automaticamente se o `proxy/runtime` nao estiver protegido com PyArmor.
- O script valida:
  - existencia de `proxy/runtime/pyarmor_runtime_000000/pyarmor_runtime.so`
  - marcador `__pyarmor__` em todos os `.py` dentro de `proxy/runtime`
- Fluxo obrigatorio antes do publish:

```bash
bash /ariusmonitor/build/build_protegido.sh
```
