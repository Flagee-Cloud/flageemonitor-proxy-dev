# Proxy Shared Layer

Camada comum entre providers.

## Itens esperados

- action dispatcher e resolver de aliases
- scheduler e plano de execucao
- cliente ssh e politicas de retry
- pipeline de logs/metricas de action
- utilitarios de checksum e assets

## Contrato

A camada shared recebe `provider_id` e delega adaptacoes para o provider selecionado.
