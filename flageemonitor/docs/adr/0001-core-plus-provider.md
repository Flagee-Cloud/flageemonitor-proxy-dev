# ADR 0001: Core + Provider Adapters

## Status
Accepted

## Contexto
O sistema atual atende fortemente o contexto Arius e precisa abrir para novos providers.

## Decisao
Adotar arquitetura com core compartilhado e adaptadores por provider.

## Consequencias
- Ganho: extensao para novos providers sem duplicar proxy/server.
- Custo: exige disciplina de fronteiras entre shared e provider.
