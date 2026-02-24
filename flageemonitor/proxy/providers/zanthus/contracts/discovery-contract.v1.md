# Zanthus Discovery Contract v1

Este contrato define os campos minimos para descobrir e registrar endpoints Zanthus no proxy unico.

## Campos minimos por host

- `provider`: deve ser `zanthus`
- `host_type`: `endpoint`, `concentrator` ou `application_server`
- `hostname`: identificador unico no escopo do cliente
- `ip`: endereco primario para conexao
- `ssh_user`: usuario de automacao
- `ssh_auth`: `password` ou `key`
- `os_family`: esperado `linux`
- `os_version`: distribuicao/versao detectada
- `arch`: `x86` ou `x86_64`
- `capabilities`: lista de capacidades validas para o host

## Regra de compatibilidade

- Qualquer host sem `os_family`, `os_version` ou `arch` deve cair para modo restritivo (`compat-mode=enforce` recomendado).
- Actions nao suportadas pelo perfil devem retornar erro explicito de capability.

## Regra de naming

- O contrato externo pode manter naming Zanthus.
- O proxy deve traduzir para actions canonicas antes do dispatch.
