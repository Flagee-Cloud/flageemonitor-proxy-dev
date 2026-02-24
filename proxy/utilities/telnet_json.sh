#!/bin/bash
# Uso: telnet_json.sh [HOST] [PORT] [TIMEOUT_S]
HOST=${1}
PORT=${2}
TIMEOUT_S=${3:-5}

json() {
  # $1 up(true/false)  $2 latency_ms_or_null
  printf '{"up":%s,"latency_ms":%s,"host":"%s","port":%s}\n' "$1" "$2" "$HOST" "$PORT"
}

# Método A: alta precisão com date +%s%3N (ms)
if ms_now=$(date +%s%3N 2>/dev/null) && printf '%s' "$ms_now" | grep -Eq '^[0-9]{13,}$'; then
  start=$ms_now
  timeout "${TIMEOUT_S}" bash -c "echo > /dev/tcp/${HOST}/${PORT}" >/dev/null 2>&1
  rc=$?
  end=$(date +%s%3N)
  # Corrige wrap improvável
  if [ "$end" -lt "$start" ]; then latency=0; else latency=$(( end - start )); fi
  if [ $rc -eq 0 ]; then json true "$latency"; exit 0
  elif [ $rc -eq 124 ]; then json false null; exit 0
  else json false "$latency"; exit 0; fi
fi

# Método B: timeout + bash time (segundos com casas decimais) -> ms
if command -v timeout >/dev/null 2>&1; then
  # força separador decimal como ponto
  LC_ALL=C TIMEFORMAT='%3R'
  dur=$( { time timeout "${TIMEOUT_S}" bash -c "echo > /dev/tcp/${HOST}/${PORT}"; } 2>&1 >/dev/null )
  rc=$?
  # normaliza vírgula->ponto por segurança
  dur=$(printf '%s' "$dur" | tr ',' '.')
  if printf '%s' "$dur" | grep -Eq '^[0-9]+(\.[0-9]+)?$'; then
    # converte para ms com awk (inteiro)
    ms=$(awk -v s="$dur" 'BEGIN{printf("%d", s*1000 + 0.5)}')
  else
    ms=
  fi
  if [ $rc -eq 0 ]; then json true "${ms:-null}"; exit 0
  elif [ $rc -eq 124 ]; then json false null; exit 0
  else json false "${ms:-null}"; exit 0; fi
fi

# Método C: fallback sem timeout preciso (segundos inteiros)
start_s=$(date +%s)
bash -c "echo > /dev/tcp/${HOST}/${PORT}" >/dev/null 2>&1 &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
  now_s=$(date +%s)
  if [ $(( now_s - start_s )) -ge $TIMEOUT_S ]; then
    kill -TERM "$pid" 2>/dev/null; sleep 0.2; kill -KILL "$pid" 2>/dev/null
    json false null; exit 0
  fi
  sleep 0.1
done
wait "$pid" 2>/dev/null; rc=$?
elapsed_ms=$(( ( $(date +%s) - start_s ) * 1000 ))
if [ $rc -eq 0 ]; then json true "$elapsed_ms"; else json false "$elapsed_ms"; fi
