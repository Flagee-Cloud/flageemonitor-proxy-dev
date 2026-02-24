#!/bin/sh
# usb_printer_detect.sh — detectar **apenas impressoras físicas** no host
# Suporta: USB bruto (usblp), USB classe 07 (Printer), USB-serial (ttyACM/ttyUSB) com heurística,
# e Porta Paralela **somente** se expor ID IEEE-1284 (evita /dev/lp0 "fantasma").
# Slackware 13 e Ubuntu 14→24

# PATH mais generoso para ambiente do zabbix_agentd
PATH="$PATH:/sbin:/usr/sbin"

# Modos:
#   present                      -> imprime 1/0 se há impressora física conectada (aplica filtros)
#   get <campo> <serial|device>  -> imprime o campo da impressora selecionada
#   (sem args)                   -> JSON com **somente** impressoras físicas

# Filtros opcionais (regex egrep -i):
#   export PRN_REGEX='EPSON|ELGIN|BIXOLON'       # incluir só marcas/modelos que combinem
#   export PRN_EXCLUDE='...'                     # excluir nomes/seriais/URIs indesejados
# Padrões razoáveis p/ grandes ambientes:
#   EXCLUI: SAT/pinpad/scanner/balança/scale/ppc930/"cdc device"/gadget serial
#   ACEITA USB-serial se nome parecer "printer/thermal/receipt" etc.

MODE="${1:-json}"
GET_FIELD="$2"
SELECT="$3"

PRN_REGEX="${PRN_REGEX:-}"  # inclusão opcional
PRN_EXCLUDE="${PRN_EXCLUDE:-sat|pinpad|scanner|balan[cç]a|scale|ppc930|cdc[ _-]?device|gadget[ _-]?serial|netchip}"

# Palavras que “cheiram” a impressora (para USB-serial/CDC)
PRN_POSITIVE="${PRN_POSITIVE:-printer|thermal|receipt|tm-|i9|epson|elgin|bixolon|bematech|daruma|custom|star|hprt|datecs|sweda|rongta|gprinter|xprinter|zjiang|zebra|argox|sato|mp-?4200|itautec}"

# Opcional: whitelist por VID:PID (regex). Ex.: export PRN_VIDPID_POS='04b8:0e15|20d1:7008'
PRN_VIDPID_POS="${PRN_VIDPID_POS:-}"

KEYS_SEEN=""
seen_key() { case "|$KEYS_SEEN|" in *"|$1|"*) return 0;; *) return 1;; esac; }
add_key()  { KEYS_SEEN="$KEYS_SEEN|$1"; }
trim_right() { printf '%s' "$1" | sed 's/[[:space:]]\+$//'; }
json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# ---------- impressão de um item JSON ----------
# args: method dev bus vid pid man prod ser
print_item() {
  m="$(json_escape "$(trim_right "$1")")"
  d="$(json_escape "$(trim_right "$2")")"
  b="$(json_escape "$(trim_right "$3")")"
  v="$(json_escape "$(trim_right "$4")")"
  p="$(json_escape "$(trim_right "$5")")"
  mf="$(json_escape "$(trim_right "$6")")"
  pr="$(json_escape "$(trim_right "$7")")"
  s="$(json_escape "$(trim_right "$8")")"
  printf '{'
  printf '"method":"%s",' "$m"
  printf '"device":"%s",' "$d"
  printf '"bus":"%s",' "$b"
  printf '"vid":"%s",' "$v"
  printf '"pid":"%s",' "$p"
  printf '"manufacturer":"%s",' "$mf"
  printf '"product":"%s",' "$pr"
  printf '"serial":"%s"' "$s"
  printf '}'
}

FIRST=1
GOT=0

passes_filters() {
  man="$1"; prod="$2"; ser="$3"; dev="$4"
  if [ -n "$PRN_REGEX" ]; then
    t="$(printf '%s %s' "$man" "$prod")"
    printf '%s' "$t" | egrep -iq "$PRN_REGEX" || return 1
  fi
  if [ -n "$PRN_EXCLUDE" ]; then
    t="$(printf '%s %s %s %s' "$man" "$prod" "$ser" "$dev")"
    printf '%s' "$t" | egrep -iq "$PRN_EXCLUDE" && return 1
  fi
  return 0
}

# decide se um dispositivo “parece impressora”
# args: man prod vid pid is_usblp has_class07 is_parallel
looks_like_printer() {
  man="$1"; prod="$2"; vid="$3"; pid="$4"; is_usblp="$5"; has_class07="$6"; is_parallel="$7"
  [ "x$is_usblp"   = "x1" ] && return 0
  [ "x$has_class07" = "x1" ] && return 0
  [ "x$is_parallel" = "x1" ] && return 0
  id=""
  [ -n "$vid" ] && [ -n "$pid" ] && id="${vid}:${pid}"
  t="$(printf '%s %s %s' "$man" "$prod" "$id")"
  printf '%s' "$t" | egrep -iq "$PRN_POSITIVE" && return 0
  return 1
}

emit_json_if_needed() {
  if [ "$MODE" = "json" ]; then
    if [ $FIRST -eq 0 ]; then printf ','; else FIRST=0; fi
    print_item "$@"
  fi
}

emit() {
  method="$1"; dev="$2"; bus="$3"; vid="$4"; pid="$5"; man="$6"; prod="$7"; ser="$8"
  passes_filters "$man" "$prod" "$ser" "$dev" || return
  key="$ser"; [ -z "$key" ] && key="${vid}:${pid}@${bus}"; [ -z "$key" ] && key="$dev"
  seen_key "$key" && return
  add_key "$key"

  if [ "$MODE" = "get" ]; then
    if [ -n "$SELECT" ] && { [ "x$ser" = "x$SELECT" ] || [ "x$dev" = "x$SELECT" ]; }; then
      case "$GET_FIELD" in
        json)              print_item "$method" "$dev" "$bus" "$vid" "$pid" "$man" "$prod" "$ser"; printf '\n'; GOT=1 ;;
        device)            printf '%s\n' "$dev";        GOT=1 ;;
        method)            printf '%s\n' "$method";     GOT=1 ;;
        bus)               printf '%s\n' "$bus";        GOT=1 ;;
        vid)               printf '%s\n' "$vid";        GOT=1 ;;
        pid)               printf '%s\n' "$pid";        GOT=1 ;;
        manufacturer|mfr)  printf '%s\n' "$(trim_right "$man")";  GOT=1 ;;
        product|model)     printf '%s\n' "$(trim_right "$prod")"; GOT=1 ;;
        serial)            printf '%s\n' "$ser";        GOT=1 ;;
        present)           printf '1\n';                GOT=1 ;;
      esac
    fi
    return
  fi

  emit_json_if_needed "$method" "$dev" "$bus" "$vid" "$pid" "$man" "$prod" "$ser"
}

# ---------- coletar infos de uma TTY (ACM/USB/alias) ----------
emit_tty() {
  p="$1"
  base="$(basename "$p")"
  link="$(readlink "$p" 2>/dev/null)"
  [ -n "$link" ] && devname="$(basename "$link")" || devname="$base"

  sys="/sys/class/tty/$devname/device"
  bus=''; vid=''; pid=''; man=''; prod=''; ser=''; found_id=0; has07=0
  if [ -e "$sys" ]; then
    up="$sys"; i=0
    while [ $i -lt 8 ]; do
      if [ -r "$up/idVendor" ]; then found_id=1; break; fi
      up="$up/.."; i=$((i+1))
    done
    if [ $found_id -eq 1 ]; then
      [ -r "$up/idVendor" ]     && vid="$(cat "$up/idVendor" 2>/dev/null)"
      [ -r "$up/idProduct" ]    && pid="$(cat "$up/idProduct" 2>/dev/null)"
      [ -r "$up/manufacturer" ] && man="$(cat "$up/manufacturer" 2>/dev/null)"
      [ -r "$up/product" ]      && prod="$(cat "$up/product" 2>/dev/null)"
      [ -r "$up/serial" ]       && ser="$(cat "$up/serial" 2>/dev/null)"
      bus="$(basename "$up")"
      # há alguma interface classe 07 nesse mesmo device?
      for icls in "$(basename "$up")":*; do
        [ -r "/sys/bus/usb/devices/$icls/bInterfaceClass" ] || continue
        val="$(cat "/sys/bus/usb/devices/$icls/bInterfaceClass" 2>/dev/null)"
        [ "x$val" = "x07" ] && has07=1 && break
      done
    fi
  fi
  if command -v udevadm >/dev/null 2>&1; then
    props="$(udevadm info -q property -n "$p" 2>/dev/null)"
    [ -z "$man" ] && man="$(printf '%s\n' "$props" | egrep -m1 '^ID_VENDOR=' | cut -d= -f2)"
    [ -z "$prod" ] && prod="$(printf '%s\n' "$props" | egrep -m1 '^ID_MODEL=' | cut -d= -f2)"
    [ -z "$ser" ] && ser="$(printf '%s\n' "$props" | egrep -m1 '^ID_SERIAL=' | cut -d= -f2)"
    [ -z "$vid" ] && vid="$(printf '%s\n' "$props" | egrep -m1 '^ID_VENDOR_ID=' | cut -d= -f2)"
    [ -z "$pid" ] && pid="$(printf '%s\n' "$props" | egrep -m1 '^ID_MODEL_ID=' | cut -d= -f2)"
  fi

  # --- Apenas incluir no JSON se realmente parecer impressora (ou exceções) ---
  is_prn=0
  looks_like_printer "$man" "$prod" "$vid" "$pid" 0 "$has07" 0 && is_prn=1
  id="${vid}:${pid}"
  force=0
  if [ -n "$PRN_VIDPID_POS" ] && printf '%s' "$id" | egrep -iq "$PRN_VIDPID_POS"; then force=1; fi

  if [ "$MODE" = "json" ]; then
    if [ $is_prn -eq 1 ] || [ $has07 -eq 1 ] || [ "x$p" = "x/dev/ttyIMP" ] || [ $force -eq 1 ]; then
      emit "usb-serial" "$p" "$bus" "$vid" "$pid" "$(trim_right "$man")" "$(trim_right "$prod")" "$ser"
    fi
  fi

  # Sinal p/ modo present
  if [ "$MODE" = "present" ]; then
    [ $is_prn -eq 1 ] || [ $has07 -eq 1 ] && echo "__LIKELY_PRN__"
  fi
}

# ---------- porta paralela: só se houver ID IEEE-1284 ----------
emit_parallel_if_real() {
  dev="$1"                               # ex.: /dev/lp0
  num="$(printf '%s' "$dev" | sed 's#.*/lp##')"
  idfile="/proc/sys/dev/parport/parport${num}/deviceid"
  [ -r "$idfile" ] || return 1
  devid="$(cat "$idfile" 2>/dev/null | tr -d '\r')"
  [ -n "$devid" ] || return 1

  # Extrai MFG/MDL do IEEE-1284 (ex.: "MFG:EPSON;MDL:TM-T20;...")
  mfg="$(printf '%s\n' "$devid" | sed -n 's/.*[; ]MFG:\([^;]*\).*/\1/p' | head -n1)"
  mdl="$(printf '%s\n' "$devid" | sed -n 's/.*[; ]MDL:\([^;]*\).*/\1/p' | head -n1)"
  [ -z "$mfg" ] && mfg="Parallel"
  [ -z "$mdl" ] && mdl="IEEE1284"

  passes_filters "$mfg" "$mdl" "" "$dev" || return 1
  emit "parallel" "$dev" "" "" "" "$mfg" "$mdl" ""
  return 0
}

# ---------- POSNET: ler apenas /posnet/nfiscal*.txt (leve e seguro) ----------
posnet_ref_port() {
  dir="${POSNET_DIR:-/posnet}"
  [ -d "$dir" ] || return 1

  # pega até 5 arquivos nfiscal mais recentes
  files="$(ls -1t "$dir"/nfiscal*.txt 2>/dev/null | head -n5)"
  [ -n "$files" ] || return 1

  PATTERN='/dev/(tty(USB|ACM|S)[0-9]+|usb/lp[0-9]+|lp[0-9]+)'

  for f in $files; do
    [ -f "$f" ] || continue
    if command -v timeout >/dev/null 2>&1; then
      line="$(LC_ALL=C timeout "${POSNET_TMO:-1s}" grep -a -oE "$PATTERN" "$f" 2>/dev/null | tail -n1)"
    else
      line="$(LC_ALL=C grep -a -oE "$PATTERN" "$f" 2>/dev/null | tail -n1)"
    fi
    [ -n "$line" ] || continue

    # valida dispositivo e filtra SAT/pinpad via udev, se possível
    if [ -c "$line" ]; then
      if command -v udevadm >/dev/null 2>&1; then
        props="$(udevadm info -q property -n "$line" 2>/dev/null)"
        sig="$(printf '%s\n' "$props" | grep -E '^(ID_VENDOR|ID_MODEL|ID_SERIAL)=' | cut -d= -f2 | tr '\n' ' ')"
        if [ -n "$PRN_EXCLUDE" ] && printf '%s' "$sig" | grep -Eiq "$PRN_EXCLUDE"; then
          continue
        fi
      fi
      printf '%s\n' "$line"
      return 0
    fi
  done

  return 1
}

# ---------------- modo "present" (apenas físico) ----------------
if [ "$MODE" = "present" ]; then
  # alias estável, se existir
  if [ -e /dev/ttyIMP ]; then
    man=""; prod=""; ser=""; vid=""; pid=""
    if command -v udevadm >/dev/null 2>&1; then
      props="$(udevadm info -q property -n /dev/ttyIMP 2>/dev/null)"
      man="$(printf '%s\n' "$props" | egrep -m1 '^ID_VENDOR=' | cut -d= -f2)"
      prod="$(printf '%s\n' "$props" | egrep -m1 '^ID_MODEL=' | cut -d= -f2)"
      ser="$(printf '%s\n' "$props" | egrep -m1 '^ID_SERIAL=' | cut -d= -f2)"
      vid="$(printf '%s\n' "$props" | egrep -m1 '^ID_VENDOR_ID=' | cut -d= -f2)"
      pid="$(printf '%s\n' "$props" | egrep -m1 '^ID_MODEL_ID=' | cut -d= -f2)"
    fi
    passes_filters "$man" "$prod" "$ser" "/dev/ttyIMP" && \
    looks_like_printer "$man" "$prod" "$vid" "$pid" 0 0 0 && echo 1 && exit 0
  fi

  # usblp é impressora
  for dev in /dev/usb/lp*; do [ -c "$dev" ] && echo 1 && exit 0; done

  # classe 07 é impressora
  if grep -sl '^07$' /sys/bus/usb/devices/*:*/bInterfaceClass >/vol/null 2>&1; then echo 1; exit 0; fi
  # (acima usa /vol/null? se não existir no seu SO, troque para /dev/null)

  # 2b) Porta referenciada nos logs nfiscal => conta como impressora local
  REF_PORT="$(posnet_ref_port)"
  if [ -n "$REF_PORT" ] && [ -c "$REF_PORT" ]; then
    echo 1
    exit 0
  fi

  # USB-serial (aplica filtros + heurística)
  for p in /dev/ttyACM* /dev/ttyUSB*; do
    [ -c "$p" ] || continue
    out="$(emit_tty "$p" 2>/dev/null | tail -n1)"
    [ "x$out" = "x__LIKELY_PRN__" ] && echo 1 && exit 0
  done

  # Paralela **real** (com IEEE-1284)
  for dev in /dev/lp*; do
    [ -c "$dev" ] || continue
    emit_parallel_if_real "$dev" && echo 1 && exit 0
  done

  # (Sem CUPS aqui)
  echo 0; exit 0
fi

# ---------------- saída JSON (apenas físico) ----------------
[ "$MODE" = "json" ] && printf '{ "printers": ['

# 0) /dev/ttyIMP primeiro (se existir)
[ -e /dev/ttyIMP ] && emit_tty "/dev/ttyIMP"

# 1) USB bruto (usblp)
for dev in /dev/usb/lp*; do
  [ -c "$dev" ] || continue
  bus=''; vid=''; pid=''; man=''; prod=''; ser=''
  for cand in "/sys/class/usb/$(basename "$dev")" "/sys/class/usblp/$(basename "$dev")"; do
    [ -e "$cand/device" ] || continue
    d="$cand/device"
    for up in "$d" "$d/.." "$d/../.." "$d/../../.."; do
      [ -r "$up/idVendor" ]     && vid="$(cat "$up/idVendor" 2>/dev/null)"
      [ -r "$up/idProduct" ]    && pid="$(cat "$up/idProduct" 2>/dev/null)"
      [ -r "$up/manufacturer" ] && man="$(cat "$up/manufacturer" 2>/dev/null)"
      [ -r "$up/product" ]      && prod="$(cat "$up/product" 2>/dev/null)"
      [ -r "$up/serial" ]       && ser="$(cat "$up/serial" 2>/dev/null)"
    done
    [ -n "$vid" ] && bus="$(basename "$(dirname "$d")")" || bus=""
    break
  done
  emit "usblp" "$dev" "$bus" "$vid" "$pid" "$man" "$prod" "$ser"
done

# 1b) Paralela **real** (com IEEE-1284)
for dev in /dev/lp*; do
  [ -c "$dev" ] || continue
  emit_parallel_if_real "$dev" >/dev/null 2>&1
done

# 2) Classe 07 (Printer)
for iface in /sys/bus/usb/devices/*:*/bInterfaceClass; do
  [ -r "$iface" ] || continue
  cls="$(cat "$iface" 2>/dev/null)"; [ "x$cls" = "x07" ] || continue
  base="$(dirname "$iface")"; base="${base%:*}"
  [ -d "$base" ] || continue
  bus="$(basename "$base")"
  vid="$(cat "$base/idVendor"     2>/dev/null)"
  pid="$(cat "$base/idProduct"    2>/dev/null)"
  man="$(cat "$base/manufacturer" 2>/dev/null)"
  prod="$(cat "$base/product"     2>/dev/null)"
  ser="$(cat "$base/serial"       2>/dev/null)"
  dev_uri="usb://"; [ -n "$man" ] && dev_uri="${dev_uri}${man}/"; dev_uri="${dev_uri}${prod}"; [ -n "$ser" ] && dev_uri="${dev_uri}?serial=${ser}"
  emit "usb-class07" "$dev_uri" "$bus" "$vid" "$pid" "$man" "$prod" "$ser"
done

# 3) USB-serial (ttyACM/ttyUSB) — além de /dev/ttyIMP
for p in /dev/ttyACM* /dev/ttyUSB*; do
  [ -c "$p" ] || continue
  [ "x$p" = "x/dev/ttyIMP" ] && continue
  emit_tty "$p"
done

if [ "$MODE" = "json" ]; then
  printf '] }\n'
elif [ "$MODE" = "get" ]; then
  [ $GOT -eq 0 ] && [ "$GET_FIELD" = "present" ] && echo 0
fi

exit 0
