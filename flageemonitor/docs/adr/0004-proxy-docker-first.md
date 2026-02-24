# ADR 0004: Proxy Docker First

## Status
Accepted

## Contexto
O proxy precisa ser unico e portavel, com baixa dependencia do SO host, incluindo ambientes Windows com Docker.

## Decisao
Adotar Docker First para runtime do proxy:

- runtime principal em container,
- host-side apenas com scripts finos de bootstrap/update/run/logs,
- evitar acoplamento do core a init/pacote/path do host.

## Consequencias

- Ganho: menor variacao operacional por host e onboarding mais previsivel.
- Custo: disciplina de empacotamento e contratos de volume/rede/segredo no container.
