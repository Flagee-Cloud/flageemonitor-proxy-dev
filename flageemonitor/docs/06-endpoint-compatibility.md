# Compatibilidade de Endpoint (Client)

Este documento define requisitos obrigatorios para a ponta final (hosts cliente), onde a variabilidade de sistema operacional e alta.

## Escopo de compatibilidade atual

Distribuicoes e versoes alvo (minimo):

- Slackware 13.x (incluindo cenarios sem systemd)
- Ubuntu 14.04 ate 24.04
- Linux Mint 17.x ate 21.x
- Arquiteturas `x86_64` e `i686` (32 bits)

## Premissas de arquitetura

- Server e Proxy sao controlados pela Flagee (ambiente moderno e previsivel).
- Proxy segue modelo Docker First para reduzir dependencia de SO host.
- Client nao e controlado integralmente; deve priorizar retrocompatibilidade e degradacao graciosa.
- A ponta final deve evitar dependencias fortes em componentes ausentes em distros antigas.

## Requisitos tecnicos obrigatorios da ponta final

1. Init e servico
- Nao depender exclusivamente de systemd.
- Suportar systemd, SysV/init.d e fallback por cron quando necessario.

2. Runtime
- Preferir base POSIX shell para bootstrap e orquestracao local.
- Componentes em Python/C/Go devem ser opcionais por capability, nunca pre-requisito universal.
- Nao assumir Docker no endpoint final.

3. Arquitetura de binarios
- Publicar artefatos por arquitetura (`linux-amd64`, `linux-386`).
- Manter fallback para utilitarios legados quando 32 bits for detectado.

4. Dependencias e libc
- Minimizar dependencias dinamicas no endpoint.
- Sempre que possivel, usar binarios estaticos para utilitarios auxiliares criticos.
- Tratar incompatibilidade de glibc com fallback operacional (acao parcial + diagnostico claro).

5. Capabilities por perfil
- Cada action deve declarar suporte por SO/arquitetura.
- Dispatcher deve bloquear execucao nao suportada antes do deploy remoto.

6. Integridade e rollback
- Toda instalacao/atualizacao deve ser idempotente.
- Exigir checksum de pacote.
- Prever rollback para versao anterior em caso de falha.

## Matriz minima de suporte

Niveis:

- `L1` = suportado em producao
- `L2` = suportado com restricoes (capabilities reduzidas)
- `L3` = best effort (somente monitoramento e diagnostico)

Versao inicial recomendada:

- Slackware 13 x86_64/i686: L2
- Ubuntu 14.04/16.04 x86_64/i686: L2
- Ubuntu 18.04+ x86_64: L1
- Ubuntu 18.04+ i686: L2
- Mint 17 x86_64/i686: L2
- Mint 21 x86_64: L1

## Implicacoes para escolha de tecnologia

- Evitar acoplamento da ponta final a frameworks que exigem runtime moderno.
- Tratar a ponta final como "agent-lite + actions por capability".
- Concentrar inteligencia no Proxy/Server, mantendo endpoint mais simples e portavel.

## Proximo passo

- Materializar esta matriz em contrato versionado (`contracts/compatibility/endpoint-matrix.v1.yaml`).
- Associar cada action canonica a requisitos minimos de SO/arquitetura.
