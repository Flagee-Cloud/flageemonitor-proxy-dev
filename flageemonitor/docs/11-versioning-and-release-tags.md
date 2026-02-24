# Versioning and Release Tags

Padrao de versionamento para releases formais do FlageeMonitor.

## Formato oficial

- `flageemonitor-vMAJOR.MINOR.PATCH`
- Exemplo: `flageemonitor-v0.1.0`

## Regras semanticas

- `MAJOR`: quebra de compatibilidade (evitar enquanto houver legado ativo).
- `MINOR`: novas capacidades compativeis (novos providers, novas actions canonicas).
- `PATCH`: correcao sem mudanca de contrato.

## Checklist rapido de release (5 comandos)

```bash
cd /ariusmonitor
bash /ariusmonitor/build/build_protegido.sh
/ariusmonitor/flageemonitor/tools/release/promote_proxy_dev.sh --push
/ariusmonitor/flageemonitor/tools/release/promote_server.sh --push
/ariusmonitor/flageemonitor/proxy/scripts/docker/publish_image.sh
```

Depois, criar tag formal:

```bash
/ariusmonitor/flageemonitor/tools/release/create_release_tag.sh 0.1.0 --push
```

## Politica de CI relacionada

- Push da tag `flageemonitor-v*` aciona publish manual/tag em
  `.github/workflows/flageemonitor-manual-publish.yml`.
- Em dias normais, evitar tag para nao consumir minutos de CI desnecessariamente.
