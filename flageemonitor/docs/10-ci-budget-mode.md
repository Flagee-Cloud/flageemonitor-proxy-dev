# CI Budget Mode (GitHub Free)

Configuracao de CI/CD focada em baixo consumo de minutos no plano Free.

## Objetivo

- Evitar pipelines pesadas em cada commit/PR.
- Manter validacao minima de qualidade no fluxo diario.
- Executar build/publish apenas quando realmente necessario.

## Workflows

1. `flageemonitor-budget-checks.yml`
- Trigger: `pull_request` (somente quando ha mudanca em paths do FlageeMonitor) e `workflow_dispatch`.
- Execucao: checks rapidos (sintaxe bash e validacoes de guardrail/documentacao).
- Custo: baixo.

2. `flageemonitor-manual-publish.yml`
- Trigger: `workflow_dispatch` e push de tag `flageemonitor-v*`.
- Execucao: login no GHCR e publish de imagem via script oficial.
- Custo: medio/alto (roda apenas sob demanda).

## Politica recomendada

- PRs: apenas `flageemonitor-budget-checks`.
- Build/publish Docker: manual, em janela de release.
- Opcional: usar tag `flageemonitor-vX.Y.Z` para releases formais.

## Observacoes

- O script de publish ja bloqueia runtime sem PyArmor.
- `concurrency` ativo nos workflows para cancelar execucoes antigas.
- `timeout-minutes` reduzido para evitar consumo desnecessario.
