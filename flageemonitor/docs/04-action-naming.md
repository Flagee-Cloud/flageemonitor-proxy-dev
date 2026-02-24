# Convencao de Actions

## Padrao canonico

Usar formato:

`<verbo>_<alvo>`

Exemplos:

- `install_endpoint_agent`
- `update_endpoint_config`
- `shutdown_endpoint`
- `register_endpoints`

## Regras

- Nome deve descrever intencao, nao tecnologia local.
- Evitar termos de dominio de um unico provider (`pdv`, `arius`).
- Nomes legados continuam aceitos via alias ate deprecacao.

## Mapeamento inicial legado -> canonico

- `pdv_install` -> `install_endpoint_agent`
- `pdv_uninstall` -> `uninstall_endpoint_agent`
- `pdv_update_config` -> `update_endpoint_config`
- `pdv_update_timezone` -> `update_endpoint_timezone`
- `pdv_shutdown` -> `shutdown_endpoint`
- `pdv_test_connection` -> `test_endpoint_connection`
- `pdv_test_sudo` -> `test_endpoint_privilege`
- `pdv_atualiza_impressora` -> `refresh_endpoint_printer`
- `pdv_auto_register` -> `register_endpoints`

## Aliases genericos adicionais

- `install_host_agent` -> `install_endpoint_agent`
- `install_client_agent` -> `install_endpoint_agent`
- `uninstall_host_agent` -> `uninstall_endpoint_agent`
- `uninstall_client_agent` -> `uninstall_endpoint_agent`
- `update_host_config` -> `update_endpoint_config`
- `update_client_config` -> `update_endpoint_config`
- `update_host_timezone` -> `update_endpoint_timezone`
- `shutdown_host` -> `shutdown_endpoint`
- `test_host_connection` -> `test_endpoint_connection`
- `test_host_privilege` -> `test_endpoint_privilege`
- `refresh_host_printer` -> `refresh_endpoint_printer`
- `register_hosts` -> `register_endpoints`

## Politica de deprecacao

1. Introduz canonico + alias ativo.
2. Atualiza cron/documentacao para canonico.
3. Monitora uso de alias legado por periodo definido.
4. Remove alias apenas apos criterio de estabilidade.
