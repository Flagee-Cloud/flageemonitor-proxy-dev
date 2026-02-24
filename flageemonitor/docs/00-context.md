# Contexto Atual

## Camadas existentes

- `server/`: APIs de ingestao e dashboard, regras de negocio e integracao com Zabbix.
- `proxy/`: orquestrador no ambiente do cliente, executa actions locais/remotas.
- Hosts finais: PDV, concentrador e outros dispositivos monitorados.

## Pontos fortes atuais

- Separacao pratica entre `server` e `proxy` ja consolidada.
- Acoes versionadas no proxy (`ACTION_VERSIONS`).
- Fluxo operacional claro com Docker + cron interno + config remota.

## Limites atuais

- Nomes e contratos acoplados ao contexto Arius/PDV (`pdv_*`, `ariusmonitor`).
- Regras de host muito especificas no core, reduzindo reuso para novos providers.
- Ausencia de camada formal de provider para encapsular variacoes por software house.

## Direcao

Evoluir para FlageeMonitor com um core comum e adaptadores por provider, mantendo a operacao atual como default (`provider=arius`).
