# ADR 0002: Action Aliases para Compatibilidade

## Status
Accepted

## Contexto
Actions legadas (`pdv_*`) estao em uso em cron, scripts e operacao de clientes.

## Decisao
Introduzir actions canonicas genericas e manter aliases legados durante migracao.

## Consequencias
- Ganho: evolucao sem quebra de producao.
- Custo: janela temporaria de dupla nomenclatura.
