# ADR 0003: Compatibilidade Maxima no Client Endpoint

## Status
Accepted

## Contexto
A ponta final possui alta heterogeneidade: Slackware 13, Ubuntu 14-24, Mint 17-21 e ambientes 32 bits.

## Decisao
Adotar estrategia "compatibility-first" no endpoint:

- bootstrap em POSIX shell,
- suporte a multiplos init systems,
- artefatos por arquitetura,
- degradacao graciosa por capability.

## Consequencias

- Ganho: maior cobertura real em campo sem duplicar proxy/server.
- Custo: mais disciplina de matriz de suporte e testes por capacidade.
