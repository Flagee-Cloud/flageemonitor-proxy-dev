# Modelo de Provider

## Conceito

`provider` representa a software house (Arius, Zanthus, etc).

O provider define:

- como descobrir endpoints;
- como interpretar naming e metadados;
- como montar payloads e comandos especificos;
- quais capacidades sao suportadas por perfil de host.

## Contrato minimo do provider

- `provider_id`: identificador imutavel (`arius`, `zanthus`).
- `host_profiles`: perfis aceitos (`checkout_linux`, `hub_linux`, `icmp_device`).
- `capabilities`: lista de actions canonicas suportadas por perfil.
- `asset_map`: arquivos/pacotes necessarios por action.
- `naming_rules`: regras de composicao e parsing de host.

## Politica de fallback

- Se `provider` ausente no config: assumir `arius` (compatibilidade).
- Se capability nao suportada: retornar erro funcional claro e auditavel.
- Se action legada recebida: resolver via alias para action canonica.

## Beneficio

O core permanece unico; variacoes entram apenas onde realmente diferem.
