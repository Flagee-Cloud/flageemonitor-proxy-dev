#!/bin/bash

# Defina a data de início
data_inicio="2024-01-03"

# Obtenha a data de hoje
data_hoje=$(date +%Y-%m-%d)

while [[ "$data_inicio" < "$data_hoje" ]]; do
    # Defina as datas com o horário para o comando
    inicio="${data_inicio} 00:00:00"
    fim="${data_inicio} 23:59:59"
    
    # Execute o comando com a data atual
    ./ConnectAriusServerNFCE.sh "$inicio" "$fim"
    
    # Incrementa a data em um dia
    data_inicio=$(date -I -d "$data_inicio + 1 day")
done
