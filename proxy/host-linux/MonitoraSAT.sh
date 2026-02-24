#!/bin/bash

# Definindo o caminho das bibliotecas
export LD_LIBRARY_PATH=/ariusmonitor/libs/32-bits:/posnet:$LD_LIBRARY_PATH
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin

cd /ariusmonitor

# Comando padrão para o programa 32 bits
COMANDO="/ariusmonitor/MonitoraSATc"

# Função para verificar a arquitetura da biblioteca usando readelf e grep
verifica_arquitetura_lib() {
    local lib_path="$1"
    if sudo /usr/bin/readelf -h "$lib_path" | grep -Eq 'Class.*ELF64|Classe.*ELF64'; then
        echo "64"
    else
        echo "32"
    fi
}

# Inicializa variáveis
LIB_PATH=""
FABRICANTE=""
CODIGO=""
ARGS=()

# Verifica os argumentos passados
while [[ $# -gt 0 ]]; do
    case "$1" in
        --fabricante)
            if [[ -n "$2" && "$2" != "--codigo" && "$2" != "--lib" && "$2" != *"{"* ]]; then
                FABRICANTE="$2"
                ARGS+=("--fabricante" "$FABRICANTE")
                shift 2
            else
                shift 1
            fi
            ;;
        --codigo)
            if [[ -n "$2" && "$2" != "--fabricante" && "$2" != "--lib" && "$2" != *"{"* ]]; then
                CODIGO="$2"
                ARGS+=("--codigo" "$CODIGO")
                shift 2
            else
                shift 1
            fi
            ;;
        --lib)
            if [[ -n "$2" && "$2" != "--fabricante" && "$2" != "--codigo" && "$2" != *"{"* ]]; then
                LIB_PATH="$2"
                ARGS+=("--lib" "$LIB_PATH")
                shift 2
            else
                shift 1
            fi
            ;;
        *)
            shift
            ;;
    esac
done

# Se o caminho da biblioteca foi definido, verifica a arquitetura e ajusta o comando
if [[ -n "$LIB_PATH" ]]; then
    ARQUITETURA=$(verifica_arquitetura_lib "$LIB_PATH")

    if [ "$ARQUITETURA" == "64" ]; then
        COMANDO="/ariusmonitor/MonitoraSATc64"
    fi
fi

# Echo para debug, verificar o comando e os argumentos que serão executados
# echo "$COMANDO ${ARGS[@]}"

# Executar o comando correto
if [ -f /etc/slackware-version ]; then
    if pgrep -x "MonitoraSATc" >/dev/null 2>&1; then
        echo "123456" | su -c "pkill -f 'MonitoraSATc'" 2>/dev/null
        sleep 2
    fi
    CMD="echo 123456 | su -c '$COMANDO ${ARGS[@]}'"
    eval "$CMD"
else
    if sudo /usr/bin/pgrep -x "MonitoraSATc" >/dev/null 2>&1; then
        sudo /usr/bin/pkill -f "MonitoraSATc" 2>/dev/null
        sleep 2
    fi
    sudo $COMANDO "${ARGS[@]}"
fi
