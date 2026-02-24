# Arquitetura Alvo

## Visao

Um unico produto FlageeMonitor, com:

- `server` unico para ingestao, configuracao e observabilidade.
- `proxy` unico para orquestracao local e execucao de actions, em modelo Docker First.
- ponta final modular por `provider` e `host profile`.

## Camadas

1. Business Layer (Core)
- Casos de uso de monitoramento, manutencao e automacao.
- Politicas comuns de seguranca, retries, idempotencia e auditoria.

2. Provider Layer (Adapters)
- Encapsula diferencas de arquitetura por software house.
- Define parsers, discovery, mapeamento de assets e naming local.

3. Host Profile Layer
- Regras por tipo de endpoint: checkout endpoint, hub endpoint, icmp device.
- Catalogo de capacidades suportadas por perfil.

4. Runtime Layer
- Scheduler, dispatcher de actions, execucao local/remota e logs.
- No proxy, runtime empacotado em container para reduzir acoplamento ao SO host.

## Modelo de runtime do proxy

- Docker First: o runtime principal do proxy deve rodar em container.
- Host-agnostic: o host precisa apenas de runtime de container compativel (Docker Engine/compat).
- Compatibilidade host: priorizar execucao tambem em ambientes Windows com Docker.
- Dependencias no host devem ser minimas e estaveis (rede, volume, credenciais e comando de run).

## Regras de fronteira

- Core nao conhece detalhes especificos de provider.
- Adapter nao reimplementa runtime comum.
- Provider novo nao deve exigir fork de proxy nem de server.

## Modelo de extensao

- Novo provider: adiciona pasta em `proxy/providers/<provider>` e mapeamentos no server.
- Novo host profile: adiciona perfil em catalogo comum e capabilities.
- Nova action: entra no catalogo canonicamente, com alias legados quando necessario.
