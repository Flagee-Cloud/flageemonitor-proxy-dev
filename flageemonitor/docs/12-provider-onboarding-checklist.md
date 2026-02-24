# Provider Onboarding Checklist

Checklist padrao para adicionar um novo provider sem quebrar os existentes.

## Fase 1 - Contratos

1. Criar perfil de endpoint por SO/arquitetura em `proxy/providers/<provider>/contracts/endpoint-profiles.v1.yaml`.
2. Definir contrato de discovery em `proxy/providers/<provider>/contracts/discovery-contract.v1.md`.
3. Registrar a traducao de naming externo para actions canonicas.

## Fase 2 - Runtime

1. Implementar adaptador provider-only (sem alterar `shared/`).
2. Reusar actions canonicas sempre que possivel.
3. Criar override apenas quando houver diferenca real de provider.
4. Habilitar rollout inicial em `0%` e subir gradualmente (`5%`, `20%`, `50%`, `100%`).

## Fase 3 - Compatibilidade

1. Validar matrix de compatibilidade por perfil (`x86`, `x86_64`, Linux legado/moderno).
2. Rodar em `compat-mode=warn` no inicio.
3. Migrar para `compat-mode=enforce` apos estabilidade.

## Fase 4 - Release

1. Regenerar runtime protegido (`build_protegido.sh`).
2. Promover `proxy-dev`, `server`, `proxy`.
3. Publicar tag `flageemonitor-vMAJOR.MINOR.PATCH`.

## Regra de seguranca

- Nenhum provider novo pode introduzir dependencia obrigatoria de SO no proxy host.
- Nenhum provider novo pode bypassar validacao de compatibilidade.
- Nenhum script Python deve ser distribuido sem PyArmor no deploy.
