# Business Layer

A camada de negocio define o que o produto faz, independente de provider.

## Capacidades de negocio

- Descoberta e cadastro de endpoints.
- Instalacao/atualizacao/remocao de agente.
- Coleta e envio de eventos de operacao.
- Ajustes operacionais remotos (config, timezone, shutdown, diagnostico).
- Observabilidade operacional (status, trigger, versoes, falhas).

## Casos de uso nucleares

1. Provisionar endpoint
- Entrada: endpoint alvo + perfil + provider + credenciais.
- Saida: agente instalado/configurado e endpoint registrado.

2. Manter endpoint conforme politica
- Entrada: politica ativa (config/timezone/versao).
- Saida: conformidade aplicada de forma idempotente.

3. Executar rotina periodica
- Entrada: agenda + action canonica.
- Saida: execucao auditavel com status por host.

4. Diagnosticar falha
- Entrada: endpoint com trigger/erro.
- Saida: diagnostico com causa e acao recomendada.

## Requisitos nao funcionais

- Compatibilidade retroativa para actions legadas.
- Seguranca de token por escopo (read x write).
- Rastreamento de versao da action em toda execucao.
- Escalabilidade por paralelismo controlado no proxy.
