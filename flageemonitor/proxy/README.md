# Proxy Foundation

Proxy unico para todos os providers.
Modelo de execucao: Docker First.

## Objetivo

- Manter um runtime comum para scheduler, dispatch, ssh, logs e observabilidade.
- Isolar variacoes de provider apenas em adaptadores.
- Minimizar dependencias do SO host para ampliar portabilidade (incluindo hosts Windows com Docker).

## Estrutura

- `shared/`: componentes comuns (runtime, transportes, politicas, contratos).
- `providers/`: implementacoes especificas por provider.
- `bootstrap/`: scripts host-side minimos para subir e operar o runtime em container.

## Regra principal

Nada em `shared/` pode depender de `providers/<nome>`.

## Regras de runtime

- O runtime principal deve ser executado via container.
- Scripts host-side devem ser finos (bootstrap, update, run, logs).
- Evitar acoplamento a particularidades do host (path, init, pacote).
