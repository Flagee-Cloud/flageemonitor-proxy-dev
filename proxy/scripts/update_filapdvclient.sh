#!/bin/bash
# update.sh <novo_binario> <executavel_atual>
NOVO_BINARIO=$1
EXEC_ATUAL=$2

# Aguarda alguns segundos para garantir que o processo atual encerrou
sleep 2

# Substitui o executável antigo pelo novo
mv $NOVO_BINARIO $EXEC_ATUAL
chmod +x $EXEC_ATUAL

# Reinicia o client em background
./$EXEC_ATUAL &