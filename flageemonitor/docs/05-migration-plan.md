# Plano de Migracao

## Objetivo

Migrar AriusMonitor para FlageeMonitor em fases, sem interromper clientes em producao.

## Fase 0 - Baseline e seguranca

- Congelar fluxo atual e registrar metricas baseline.
- Garantir testes de regressao para actions criticas.
- Definir indicadores de sucesso por release.

## Fase 1 - Contratos e aliases

- Adicionar catalogo canonico de actions.
- Introduzir `ACTION_ALIASES` sem remover nomes legados.
- Registrar nos logs action recebida e action resolvida.

## Fase 2 - Proxy Docker First

- Consolidar runtime do proxy em container como caminho padrao.
- Reduzir scripts host-side para bootstrap/update/execucao.
- Garantir operacao com dependencia minima do SO host (incluindo Windows com Docker).

## Fase 3 - Provider abstraction

- Incluir `provider` no config de cliente (default `arius`).
- Extrair regras provider-specific para adaptadores.
- Manter comportamento legado com provider default.

## Fase 4 - Estrutura de codigo

- Criar `proxy/providers/<provider>` e `proxy/shared` no runtime novo.
- Mover regras comuns para shared gradualmente.
- Manter wrappers legados enquanto houver dependencia.

## Fase 5 - Branding dual

- Introduzir nomes FlageeMonitor (imagem, scripts e docs).
- Manter aliases `ariusmonitor-*` funcionando.
- Comunicar deprecacao com janela clara.

## Fase 6 - Onboarding de novo provider

- Implementar provider piloto (`zanthus`) no modelo novo.
- Rodar canario controlado e validar operacao.
- Expandir por lotes apos estabilidade.

## Guardrails de producao

- Nao alterar comportamento default sem flag.
- Toda mudanca deve ter rollback simples.
- Compatibilidade e observabilidade sao criterios de aceite.
