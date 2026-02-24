# Provider Zanthus

Placeholder inicial para onboarding do provider Zanthus.

## Proximo passo

- Definir naming de endpoints.
- Definir discovery/registro.
- Definir capabilities suportadas por perfil.
- Mapear assets e comandos de manutencao.

## Artefatos iniciais

- `contracts/endpoint-profiles.v1.yaml`: perfis de host por SO/arquitetura.
- `contracts/action-overrides.v1.yaml`: pontos de extensao por action.
- `contracts/discovery-contract.v1.md`: contrato minimo de descoberta.
- `contracts/action-translation.v1.yaml`: traducao naming externo Zanthus -> canônico.

## Rollout controlado

No runtime, o provider pode ser habilitado gradualmente por host com:

- `PARAM_ROLLOUT_ZANTHUS` (0-100), ou
- `PARAM_PROVIDER_ROLLOUT={"zanthus": <0-100>}`

Sem configuracao explicita, o rollout de `zanthus` fica em `0%` por seguranca.

## Regra

Implementar somente diferencas de provider; reutilizar runtime shared.
