# FlageeMonitor Foundation

Este diretorio inicia a fundacao do FlageeMonitor, evoluindo do AriusMonitor para um modelo multi-provider sem quebrar a operacao atual.

## Objetivo

- Unificar Server e Proxy em uma base extensivel.
- Suportar multiplas software houses (providers) no mesmo produto.
- Isolar variacoes por provider apenas na ponta final (agentes/endpoints).
- Preservar compatibilidade com o legado `ariusmonitor` durante toda a migracao.

## Principios

- Compatibilidade primeiro: sem breaking change no caminho atual.
- Core estavel: negocio e orquestracao ficam em camadas compartilhadas.
- Extensao por provider: diferencas entram como adaptadores.
- Contratos explicitos: schema de config, catalogo de actions e aliases.
- Observabilidade obrigatoria: versao, logs e trilha de execucao por action.
- Client compatibility-first: ponta final com suporte a Linux legado e 32 bits.
- Proxy Docker First: runtime do proxy em container, minimizando dependencia do SO host.

## Estrutura Inicial

```text
flageemonitor/
├── docs/
├── contracts/
├── proxy/
│   ├── providers/
│   └── shared/
└── server/
```

## Estado da migracao

- Esta fundacao e documental/estrutural.
- Nenhum fluxo de producao do `ariusmonitor` foi alterado nesta fase.
- O proximo passo e conectar esta estrutura ao runtime atual por etapas controladas.

Veja o plano em `docs/05-migration-plan.md` e a diretriz de endpoint em `docs/06-endpoint-compatibility.md`.
Modelo de repositorios: `docs/07-repositories-and-access.md`.
